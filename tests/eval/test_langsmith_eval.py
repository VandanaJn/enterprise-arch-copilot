"""LangSmith offline evaluation harness.

Loads the golden set (~103 examples, 8 categories) from tests/eval/golden_set.json
and runs the evaluators defined in tests/eval/evaluators.py (deterministic
keyword/retrieval graders + three LLM-as-judge graders).

The dataset is persistent: it lives in the LangSmith account as
`eac-copilot-golden-v2` (v1 kept for historical experiments; v2 adds
expected_sources / expected_not_found and the negative / adversarial-scope
categories). The dataset is created on first run and updated on subsequent runs
(examples re-uploaded if the local JSON changed).

Quick mode (`EAC_EVAL_QUICK=1`) runs 2 examples per category with the free
deterministic evaluators only, for fast CI parity. Full local runs cost a few
dollars in OpenAI credits.

Requires: OPENAI_API_KEY, LANGSMITH_API_KEY, engineering_data.db, and chroma_db/.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from langchain_core.messages import HumanMessage
from langsmith import Client, evaluate, traceable

from src import config

# .env is loaded in tests/conftest.py before this module is imported.
from src.agent import create_enterprise_copilot
from src.citations import extract_retrieved_sources
from tests.eval.evaluators import ALL_EVALUATORS, DETERMINISTIC_EVALUATORS
from tests.eval.run_report import format_summary, summarize_results, write_report

GOLDEN_SET_PATH = Path(__file__).parent / "golden_set.json"
DATASET_NAME = "eac-copilot-golden-v2"


# --- Skip-if-prereqs-missing --------------------------------------------------


def _valid_openai_key() -> bool:
    k = os.getenv("OPENAI_API_KEY")
    return bool(k) and k != "your_openai_api_key_here"


def _has_langsmith() -> bool:
    return bool(os.getenv("LANGSMITH_API_KEY"))


def _has_local_assets() -> bool:
    return os.path.isdir(config.chroma_dir()) and os.path.isfile(config.db_file())


def _skip_reason() -> str | None:
    if not _valid_openai_key():
        return "OPENAI_API_KEY missing or still set to placeholder in .env"
    if not _has_langsmith():
        return "LANGSMITH_API_KEY missing in .env"
    if not _has_local_assets():
        bits = []
        if not os.path.isfile(config.db_file()):
            bits.append(f"SQLite DB not found: {config.db_file()}")
        if not os.path.isdir(config.chroma_dir()):
            bits.append(f"Chroma dir not found: {config.chroma_dir()}")
        return "; ".join(bits) + ". Run `make setup` (or `python -m scripts.setup`)."
    return None


_SKIP = _skip_reason()
pytestmark = [
    pytest.mark.langsmith_eval,
    pytest.mark.skipif(_SKIP is not None, reason=_SKIP or "unknown"),
]


@pytest.fixture(scope="module", autouse=True)
def _use_real_corpus():
    """Point the eval at the real corpus, not the unit-test sandbox.

    tests/conftest.py's session-autouse fixture redirects EAC_* paths to
    tests/test_data/ for every session that includes tests/ (pytest loads ancestor
    conftests even for `pytest tests/eval/`). Evals must run against the real
    chroma_db/ and engineering_data.db, so this fixture removes the overrides for
    the duration of the module and restores them afterwards.
    """
    overrides = ("EAC_DOCS_DIR", "EAC_DB_FILE", "EAC_CHROMA_DIR")
    saved = {var: os.environ.pop(var) for var in overrides if var in os.environ}
    yield
    os.environ.update(saved)


# --- Target function ----------------------------------------------------------


@traceable(name="eac_copilot_eval_target", run_type="chain")
def copilot_target(inputs: dict) -> dict:
    graph = create_enterprise_copilot()
    result = graph.invoke({"messages": [HumanMessage(content=inputs["question"])]})
    return {
        "output": result["messages"][-1].content,
        # Doc-ID stems the agent actually retrieved, letting retrieval_recall/precision
        # separate retrieval failures from generation failures.
        "retrieved_sources": extract_retrieved_sources(result["messages"]),
    }


# --- Dataset management -------------------------------------------------------


def _load_golden_set() -> list[dict]:
    raw = json.loads(GOLDEN_SET_PATH.read_text(encoding="utf-8"))
    is_quick = os.getenv("EAC_EVAL_QUICK") == "1"
    if is_quick:
        # Take a representative slice across categories for fast CI runs.
        seen: dict[str, int] = {}
        out = []
        for ex in raw:
            cat = ex["category"]
            if seen.get(cat, 0) >= 2:
                continue
            seen[cat] = seen.get(cat, 0) + 1
            out.append(ex)
        return out
    return raw


def _to_example(row: dict) -> dict:
    """Convert a golden_set.json row into a LangSmith example dict."""
    return {
        "inputs": {"question": row["question"]},
        "outputs": {
            "expected_keywords": row.get("expected_keywords", []),
            "reference_facts": row.get("reference_facts", ""),
            "expected_decline": bool(row.get("expected_decline", False)),
            "expected_sources": row.get("expected_sources", []),
            "expected_not_found": bool(row.get("expected_not_found", False)),
        },
        "metadata": {
            "id": row["id"],
            "category": row["category"],
        },
    }


@pytest.fixture(scope="session")
def persistent_dataset() -> str:
    """Create or update the persistent LangSmith dataset and return its name."""
    client = Client()
    examples = [_to_example(row) for row in _load_golden_set()]

    # Create the dataset if it doesn't exist; otherwise wipe and re-seed examples.
    try:
        existing = client.read_dataset(dataset_name=DATASET_NAME)
        # Refresh examples to match the local JSON. Cheaper than diffing per-row.
        for ex in client.list_examples(dataset_id=existing.id):
            client.delete_example(ex.id)
    except Exception:
        client.create_dataset(
            DATASET_NAME,
            description=(
                "Enterprise Architecture Copilot golden eval set v2: factual lookups, "
                "single-hop docs, multi-hop incidents, ambiguous queries, "
                "supersession-aware queries, negative (not-found) cases, and "
                "out-of-scope / adversarial-scope refusals. v2 adds expected_sources "
                "and expected_not_found annotations."
            ),
        )

    client.create_examples(dataset_name=DATASET_NAME, examples=examples)
    return DATASET_NAME


# --- The actual eval test -----------------------------------------------------


def _combined_category_mean(summary: dict, categories: tuple[str, ...], key: str) -> float | None:
    """n-weighted mean of one evaluator across several categories."""
    total, n = 0.0, 0
    for cat in categories:
        cell = (summary.get("per_category") or {}).get(cat, {}).get(key)
        if cell and cell["mean"] is not None:
            total += cell["mean"] * cell["n"]
            n += cell["n"]
    return total / n if n else None


def test_langsmith_evaluate_copilot(persistent_dataset: str):
    """Run all evaluators against the golden set; fail if scores fall below thresholds."""
    is_quick = os.getenv("EAC_EVAL_QUICK") == "1"
    evaluators = DETERMINISTIC_EVALUATORS if is_quick else ALL_EVALUATORS

    metadata: dict[str, str] = {"mode": "quick" if is_quick else "full"}
    if sha := os.getenv("GITHUB_SHA"):
        metadata["github_sha"] = sha

    results = evaluate(
        copilot_target,
        data=persistent_dataset,
        evaluators=evaluators,
        experiment_prefix="eac-copilot",
        description="Enterprise Architecture Copilot evaluation run",
        metadata=metadata,
        max_concurrency=2,
    )

    summary = summarize_results(results)
    print("\n" + format_summary(summary))
    report_path = write_report(summary)
    print(f"Report written to {report_path}")

    means = summary["per_evaluator_means"]

    def _mean_of(key: str) -> float:
        return means.get(key) or 0.0

    # Acceptance thresholds. These are deliberately loose for the first run; tighten
    # over time as the agent improves. EAC_EVAL_MIN_SCORE overrides per-key floor.
    floor = float(os.getenv("EAC_EVAL_MIN_SCORE", "0.5"))
    retrieval_floor = float(os.getenv("EAC_EVAL_RETRIEVAL_MIN", "0.6"))
    decline_floor = float(os.getenv("EAC_EVAL_DECLINE_MIN", "0.9"))

    kw = _mean_of("keyword_coverage")
    assert kw >= floor, f"keyword_coverage mean {kw:.2f} below floor {floor}"

    rr = _mean_of("retrieval_recall")
    assert rr >= retrieval_floor, f"retrieval_recall mean {rr:.2f} below floor {retrieval_floor}"

    if not is_quick:
        gr = _mean_of("groundedness")
        fa = _mean_of("factuality")
        de = _mean_of("appropriate_decline")
        assert gr >= floor, f"groundedness mean {gr:.2f} below floor {floor}"
        assert fa >= floor, f"factuality mean {fa:.2f} below floor {floor}"
        assert de >= 0.75, f"appropriate_decline mean {de:.2f} below 0.75"

        # Hard floor where a miss is unacceptable: declining out-of-scope input,
        # including adversarial phrasings dressed in PayLane vocabulary.
        decline_mean = _combined_category_mean(
            summary, ("out-of-scope", "adversarial-scope"), "appropriate_decline"
        )
        assert decline_mean is not None, "no appropriate_decline scores for decline categories"
        assert decline_mean >= decline_floor, (
            f"appropriate_decline over out-of-scope + adversarial-scope is "
            f"{decline_mean:.2f}, below floor {decline_floor}"
        )
