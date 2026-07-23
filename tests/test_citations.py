"""Unit tests for src/citations.py and the deterministic retrieval evaluators.

Pure tests: no API keys, no vector store. ToolMessages are fabricated to match
the format search_engineering_docs emits (both sides use format_doc_result, so
these tests also guard the format/parser contract).
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from src.citations import (
    SEARCH_DOCS_TOOL_NAME,
    extract_cited_sources,
    extract_retrieved_sources,
    format_doc_result,
    source_stem,
)
from tests.eval.evaluators import citation_validity, retrieval_precision, retrieval_recall

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


# --- format_doc_result includes a Cite-as tag -------------------------------------


def test_format_doc_result_includes_cite_tag():
    block = format_doc_result(1, "runbook", "docs/runbooks/001-checkout-504-mitigation.md", "body")
    assert "Cite as: [001-checkout-504-mitigation]" in block
    # still parseable by the retrieved-source extractor
    msg = ToolMessage(content=block, name=SEARCH_DOCS_TOOL_NAME, tool_call_id="c1")
    assert extract_retrieved_sources([msg]) == ["001-checkout-504-mitigation"]


def test_format_doc_result_renders_an_optional_note_without_breaking_parsing():
    block = format_doc_result(
        1,
        "adr",
        "docs/adrs/001-rabbitmq-inter-service-messaging.md",
        "body",
        note="Status: superseded by ADR-002",
    )
    lines = block.splitlines()
    assert lines[1] == "Cite as: [001-rabbitmq-inter-service-messaging]"
    assert lines[2] == "Status: superseded by ADR-002"
    msg = ToolMessage(content=block, name=SEARCH_DOCS_TOOL_NAME, tool_call_id="c1")
    assert extract_retrieved_sources([msg]) == ["001-rabbitmq-inter-service-messaging"]


# --- extract_cited_sources --------------------------------------------------------


def test_extract_cited_sources_finds_bracketed_stems():
    answer = (
        "The runbook [001-checkout-504-mitigation] covers 504s and ADR "
        "[002-adopt-kafka-event-streaming] explains Kafka.\n\n**Sources:** "
        "[001-checkout-504-mitigation], [002-adopt-kafka-event-streaming]"
    )
    assert extract_cited_sources(answer) == [
        "001-checkout-504-mitigation",
        "002-adopt-kafka-event-streaming",
    ]


def test_extract_cited_sources_ignores_markdown_links_and_plain_words():
    answer = "See [the docs](https://example.com) and [note] but cite [rb-004-kafka-lag]."
    assert extract_cited_sources(answer) == ["rb-004-kafka-lag"]


def test_extract_cited_sources_empty():
    assert extract_cited_sources("No citations here.") == []


# --- citation_validity evaluator --------------------------------------------------


def _citation_row(output: str, retrieved: list[str]) -> dict:
    return citation_validity(
        {"question": "q"}, {}, {"output": output, "retrieved_sources": retrieved}
    )


def test_citation_validity_all_backed():
    row = _citation_row(
        "Per [001-checkout-504-mitigation], restart the pods.",
        ["001-checkout-504-mitigation", "004-kafka-consumer-lag-spike"],
    )
    assert row["score"] == 1.0


def test_citation_validity_hallucinated_citation():
    row = _citation_row(
        "See [999-made-up-doc] and [001-checkout-504-mitigation].",
        ["001-checkout-504-mitigation"],
    )
    assert row["score"] == 0.5


def test_citation_validity_skipped_when_nothing_cited():
    row = _citation_row("checkout-service is on v3.2.0.", ["001-checkout-504-mitigation"])
    assert row["score"] is None
