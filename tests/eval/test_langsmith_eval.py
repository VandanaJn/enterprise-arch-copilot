"""LangSmith offline evaluation harness.

Loads the 50-example golden set from tests/eval/golden_set.json and runs four
evaluators (keyword_coverage + three LLM-as-judge graders defined in
tests/eval/evaluators.py).

The dataset is persistent: it lives in the LangSmith account as
`eac-copilot-golden-v1`, so experiments across commits are comparable in the UI.
The dataset is created on first run and updated on subsequent runs (examples
re-uploaded if the local JSON changed).

Quick mode (`EAC_EVAL_QUICK=1`) runs only 10 examples × keyword_coverage
for fast CI parity. Full local runs cost ~$1-2 in OpenAI credits.

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
from tests.eval.evaluators import (
    ALL_EVALUATORS,
    keyword_coverage,
)

GOLDEN_SET_PATH = Path(__file__).parent / "golden_set.json"
DATASET_NAME = "eac-copilot-golden-v1"


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


# --- Target function ----------------------------------------------------------


@traceable(name="eac_copilot_eval_target", run_type="chain")
def copilot_target(inputs: dict) -> dict:
    graph = create_enterprise_copilot()
    result = graph.invoke({"messages": [HumanMessage(content=inputs["question"])]})
    return {"output": result["messages"][-1].content}


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
        return out[:12]
    return raw


def _to_example(row: dict) -> dict:
    """Convert a golden_set.json row into a LangSmith example dict."""
    return {
        "inputs": {"question": row["question"]},
        "outputs": {
            "expected_keywords": row.get("expected_keywords", []),
            "reference_facts": row.get("reference_facts", ""),
            "expected_decline": bool(row.get("expected_decline", False)),
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
                "Enterprise Architecture Copilot golden eval set: factual lookups, "
                "single-hop docs, multi-hop incidents, ambiguous queries, "
                "supersession-aware queries, and out-of-scope refusals."
            ),
        )

    client.create_examples(dataset_name=DATASET_NAME, examples=examples)
    return DATASET_NAME


# --- The actual eval test -----------------------------------------------------


def test_langsmith_evaluate_copilot(persistent_dataset: str):
    """Run all evaluators against the golden set; fail if scores fall below thresholds."""
    is_quick = os.getenv("EAC_EVAL_QUICK") == "1"
    evaluators = [keyword_coverage] if is_quick else ALL_EVALUATORS

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

    # Aggregate per-evaluator scores
    per_eval: dict[str, list[float]] = {}
    for row in results:
        ev = row.get("evaluation_results")
        if not ev:
            continue
        for r in ev["results"]:
            if r.score is None:
                continue
            per_eval.setdefault(r.key, []).append(float(r.score))

    print("\n=== Evaluation summary ===")
    for key, scores in sorted(per_eval.items()):
        avg = sum(scores) / len(scores) if scores else 0.0
        print(f"  {key:24s} mean={avg:.2f}  n={len(scores)}")

    # Acceptance thresholds. These are deliberately loose for the first run; tighten
    # over time as the agent improves. EAC_EVAL_MIN_SCORE overrides per-key floor.
    floor = float(os.getenv("EAC_EVAL_MIN_SCORE", "0.5"))
    if not is_quick:
        kw = sum(per_eval.get("keyword_coverage", [])) / max(
            len(per_eval.get("keyword_coverage", [])) or 1, 1
        )
        gr = sum(per_eval.get("groundedness", [])) / max(
            len(per_eval.get("groundedness", [])) or 1, 1
        )
        fa = sum(per_eval.get("factuality", [])) / max(len(per_eval.get("factuality", [])) or 1, 1)
        de = sum(per_eval.get("appropriate_decline", [])) / max(
            len(per_eval.get("appropriate_decline", [])) or 1, 1
        )
        assert kw >= floor, f"keyword_coverage mean {kw:.2f} below floor {floor}"
        assert gr >= floor, f"groundedness mean {gr:.2f} below floor {floor}"
        assert fa >= floor, f"factuality mean {fa:.2f} below floor {floor}"
        assert de >= 0.75, f"appropriate_decline mean {de:.2f} below 0.75"
    else:
        kw_scores = per_eval.get("keyword_coverage", [])
        assert kw_scores, "no keyword_coverage scores recorded in quick mode"
        assert sum(kw_scores) / len(kw_scores) >= floor
