"""Unit tests for src/citations.py and the deterministic retrieval evaluators.

Pure tests: no API keys, no vector store. ToolMessages are fabricated to match
the format search_engineering_docs emits (both sides use format_doc_result, so
these tests also guard the format/parser contract).
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from src.citations import (
    SEARCH_DOCS_TOOL_NAME,
    extract_retrieved_sources,
    format_doc_result,
    source_stem,
)
from tests.eval.evaluators import retrieval_precision, retrieval_recall

# --- source_stem ----------------------------------------------------------------


def test_source_stem_posix_path():
    assert source_stem("docs/adrs/002-adopt-kafka-event-streaming.md") == (
        "002-adopt-kafka-event-streaming"
    )


def test_source_stem_windows_path():
    assert source_stem("docs\\runbooks\\001-checkout-504-mitigation.md") == (
        "001-checkout-504-mitigation"
    )


def test_source_stem_bare_name_without_extension():
    assert source_stem("001-checkout-504-mitigation") == "001-checkout-504-mitigation"


# --- extract_retrieved_sources ----------------------------------------------------


def _docs_tool_message(*sources: str) -> ToolMessage:
    blocks = [
        format_doc_result(i + 1, "adr", source, f"content of {source}")
        for i, source in enumerate(sources)
    ]
    return ToolMessage(
        content="\n\n".join(blocks), name=SEARCH_DOCS_TOOL_NAME, tool_call_id="call-1"
    )


def test_extracts_stems_from_docs_tool_message():
    messages = [
        HumanMessage(content="why kafka?"),
        _docs_tool_message(
            "docs/adrs/002-adopt-kafka-event-streaming.md",
            "docs/adrs/001-rabbitmq-inter-service-messaging.md",
        ),
        AIMessage(content="because throughput"),
    ]
    assert extract_retrieved_sources(messages) == [
        "002-adopt-kafka-event-streaming",
        "001-rabbitmq-inter-service-messaging",
    ]


def test_ignores_other_tools_and_deduplicates():
    sql_msg = ToolMessage(
        content="--- Document 1 (Type: adr, Source: docs/adrs/fake.md) ---\nnot a doc search",
        name="query_sql_database",
        tool_call_id="call-2",
    )
    messages = [
        _docs_tool_message("docs/runbooks/001-checkout-504-mitigation.md"),
        sql_msg,
        _docs_tool_message(
            "docs/runbooks/001-checkout-504-mitigation.md",
            "docs/postmortems/2024-001-black-friday-checkout-outage.md",
        ),
    ]
    assert extract_retrieved_sources(messages) == [
        "001-checkout-504-mitigation",
        "2024-001-black-friday-checkout-outage",
    ]


def test_no_docs_tool_messages_yields_empty_list():
    assert extract_retrieved_sources([HumanMessage(content="hi"), AIMessage(content="yo")]) == []


# --- retrieval_recall / retrieval_precision ---------------------------------------


def _run_evaluators(expected: list[str], retrieved: list[str]) -> tuple[dict, dict]:
    inputs = {"question": "q"}
    reference_outputs = {"expected_sources": expected}
    outputs = {"retrieved_sources": retrieved}
    return (
        retrieval_recall(inputs, reference_outputs, outputs),
        retrieval_precision(inputs, reference_outputs, outputs),
    )


def test_retrieval_perfect_match():
    recall, precision = _run_evaluators(["a-doc"], ["a-doc"])
    assert recall["score"] == 1.0
    assert precision["score"] == 1.0


def test_retrieval_partial_recall_and_precision():
    recall, precision = _run_evaluators(["a-doc", "b-doc"], ["a-doc", "c-doc", "d-doc"])
    assert recall["score"] == 0.5
    assert precision["score"] == 1.0 / 3.0


def test_retrieval_skipped_without_annotation():
    recall, precision = _run_evaluators([], ["a-doc"])
    assert recall["score"] is None
    assert precision["score"] is None


def test_retrieval_expected_but_nothing_retrieved():
    recall, precision = _run_evaluators(["a-doc"], [])
    assert recall["score"] == 0.0
    assert precision["score"] == 0.0


def test_retrieval_match_is_case_insensitive():
    recall, _ = _run_evaluators(["A-Doc"], ["a-doc"])
    assert recall["score"] == 1.0
