"""
LangSmith offline evaluations for the Enterprise Architecture Copilot.

Follows the pattern from intro-to-langsmith (module_2 experiments): `evaluate()`,
a target function, and row-level evaluators with `reference_outputs` / `outputs`.

Requires: OPENAI_API_KEY, LANGSMITH_API_KEY, engineering_data.db, and chroma_db/
(see README: generate_mock_data + build_vector_db).
"""

from __future__ import annotations

import os
import uuid

import pytest
from langchain_core.messages import HumanMessage
from langsmith import Client, evaluate, traceable

# .env is loaded in tests/conftest.py before this module is imported.
from src.agent import CHROMA_DB_DIR, DB_FILE, create_enterprise_copilot
from src.generate_mock_data import (
    create_directories,
    generate_structured_data,
    generate_unstructured_data,
)


def _valid_openai_key() -> bool:
    k = os.getenv("OPENAI_API_KEY")
    return bool(k) and k != "your_openai_api_key_here"


def _has_langsmith() -> bool:
    return bool(os.getenv("LANGSMITH_API_KEY"))


def _has_local_assets() -> bool:
    return os.path.isdir(CHROMA_DB_DIR) and os.path.isfile(DB_FILE)


def _langsmith_eval_skip_reason() -> str | None:
    if not _valid_openai_key():
        return "OPENAI_API_KEY missing or still set to placeholder in .env"
    if not _has_langsmith():
        return "LANGSMITH_API_KEY missing in .env"
    if not _has_local_assets():
        parts = []
        if not os.path.isfile(DB_FILE):
            parts.append(f"SQLite DB not found: {DB_FILE}")
        if not os.path.isdir(CHROMA_DB_DIR):
            parts.append(f"Chroma dir not found: {CHROMA_DB_DIR}")
        return (
            "; ".join(parts)
            + ". From repo root run: python src/generate_mock_data.py && python src/build_vector_db.py"
        )
    return None


_SKIP = _langsmith_eval_skip_reason()
pytestmark = [
    pytest.mark.langsmith_eval,
    pytest.mark.skipif(_SKIP is not None, reason=_SKIP or "unknown"),
]


@pytest.fixture(scope="module", autouse=True)
def setup_eval_fixtures():
    create_directories()
    generate_structured_data()
    generate_unstructured_data()
    yield
    try:
        from src.agent import close_connections

        close_connections()
    except Exception:
        pass


@traceable(name="eac_copilot_eval_target", run_type="chain")
def copilot_target(inputs: dict) -> dict:
    graph = create_enterprise_copilot()
    result = graph.invoke({"messages": [HumanMessage(content=inputs["question"])]})
    return {"output": result["messages"][-1].content}


def keyword_coverage(inputs: dict, reference_outputs: dict, outputs: dict) -> dict:
    """Fraction of reference keywords that appear in the model output (case-insensitive)."""
    text = (outputs.get("output") or "").lower()
    keywords = reference_outputs.get("keywords") or []
    if isinstance(keywords, str):
        keywords = [k.strip() for k in keywords.split(",") if k.strip()]
    question = (inputs or {}).get("question") or ""
    row: dict = {
        "key": "keyword_coverage",
        "metadata": {"question": question},
    }
    if question:
        row["comment"] = f"Question: {question}"
    if not keywords:
        row["score"] = 1.0
        return row
    hits = sum(1 for k in keywords if k.lower() in text)
    score = hits / len(keywords)
    row["score"] = score
    return row


EVAL_EXAMPLES = [
    {
        "inputs": {"question": "What version is the checkout-service currently on?"},
        "outputs": {"keywords": ["v1.4.2", "checkout"]},
    },
    {
        "inputs": {
            "question": (
                "We're seeing 504s on checkout in prod. Who owns the service and what's the mitigation?"
            )
        },
        "outputs": {"keywords": ["alpha", "mitigation"]},
    },
    {
        "inputs": {"question": "Why did we adopt Kafka for event streaming?"},
        "outputs": {"keywords": ["kafka", "event"]},
    },
    {
        "inputs": {
            "question": (
                "The /api/v1/checkout endpoint is failing with a 504. Who owns it "
                "and is there a runbook for it?"
            )
        },
        # Match integration test expectations: owner + runbook content (avoid requiring all three phrases).
        "outputs": {"keywords": ["alpha", "mitigation"]},
    },
]


@pytest.fixture()
def ephemeral_eval_dataset():
    client = Client()
    name = f"eac-copilot-eval-{uuid.uuid4().hex[:12]}"
    client.create_dataset(
        name,
        description="Ephemeral golden set for Enterprise Architecture Copilot CI evals",
    )
    try:
        client.create_examples(dataset_name=name, examples=EVAL_EXAMPLES)
        yield name
    finally:
        try:
            client.delete_dataset(dataset_name=name)
        except Exception:
            pass


def test_langsmith_evaluate_copilot(ephemeral_eval_dataset):
    min_score = float(os.getenv("EAC_EVAL_MIN_SCORE", "0.5"))
    metadata = {}
    if sha := os.getenv("GITHUB_SHA"):
        metadata["github_sha"] = sha

    results = evaluate(
        copilot_target,
        data=ephemeral_eval_dataset,
        evaluators=[keyword_coverage],
        experiment_prefix="eac-copilot",
        description="Enterprise Architecture Copilot golden-set eval (keyword coverage)",
        metadata=metadata or None,
        max_concurrency=1,
    )

    assert len(results) == len(EVAL_EXAMPLES), (
        f"expected {len(EVAL_EXAMPLES)} eval rows, got {len(results)}"
    )
    for row in results:
        ev = row["evaluation_results"]
        assert ev is not None
        for r in ev["results"]:
            assert r.score is not None
            assert r.score >= min_score
