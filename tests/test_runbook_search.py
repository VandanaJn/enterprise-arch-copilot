"""Unit tests for the planner-driven runbook search.

The runbook step replaced a ReAct sub-agent with "plan queries once, search in
parallel, hand the retrieved text straight to synthesize". These tests pin the
three things that refactor can silently break: the retrieved documents stay
visible to the retrieval evaluators as real ToolMessages, the merged payload
handed to synthesize stays bounded, and a planner failure still searches.

Pure: the search callable is injected, so no vector store and no LLM.
"""

from __future__ import annotations

import asyncio
import threading
import time

import pytest

from src.agent import (
    _asearch_docs_parallel,
    _doc_tool_messages,
    _fallback_doc_queries,
    _merge_doc_results,
    _search_docs_parallel,
)
from src.citations import extract_retrieved_sources, format_doc_result, split_doc_blocks


def _result(*sources: str) -> str:
    """One search_engineering_docs result carrying `sources`, in the real format."""
    return "\n\n".join(
        format_doc_result(i + 1, "runbook", f"docs/runbooks/{s}.md", f"body of {s}")
        for i, s in enumerate(sources)
    )


# --- block splitting ---------------------------------------------------------


def test_split_doc_blocks_recovers_each_document():
    blocks = split_doc_blocks(_result("001-checkout-504", "002-payment-timeouts"))
    assert len(blocks) == 2
    assert "001-checkout-504" in blocks[0]
    assert "002-payment-timeouts" in blocks[1]


def test_split_doc_blocks_on_empty_or_error_text():
    assert split_doc_blocks("") == []
    assert split_doc_blocks("Vector database error (boom). Fix: ...") == []


# --- merging what synthesize reads -------------------------------------------


def test_merge_doc_results_drops_blocks_repeated_across_queries():
    # Near-identical queries return the same document more than once; synthesize
    # should not pay for it twice.
    merged = _merge_doc_results([_result("001-checkout-504"), _result("001-checkout-504")])
    assert merged.count("body of 001-checkout-504") == 1


def test_merge_doc_results_renumbers_sequentially():
    merged = _merge_doc_results([_result("a-one", "b-two"), _result("c-three")])
    assert "--- Document 1 " in merged
    assert "--- Document 2 " in merged
    assert "--- Document 3 " in merged


def test_merge_doc_results_caps_block_count():
    merged = _merge_doc_results([_result("a-one", "b-two", "c-three")], max_blocks=2)
    assert "body of a-one" in merged
    assert "body of c-three" not in merged


def test_merge_doc_results_gives_every_query_a_slot_before_any_gets_a_second():
    # The planner is told to make queries complementary (mitigation vs prior
    # incidents), so a cap applied in query-major order would drop a whole query's
    # results rather than trimming each query's tail. That is how briefs lost the
    # one runbook they needed while still scoring perfectly on groundedness.
    results = [
        _result("q1-first", "q1-second", "q1-third"),
        _result("q2-first", "q2-second", "q2-third"),
        _result("q3-first", "q3-second", "q3-third"),
    ]
    merged = _merge_doc_results(results, max_blocks=3)

    assert "body of q1-first" in merged
    assert "body of q2-first" in merged
    assert "body of q3-first" in merged
    assert "body of q1-second" not in merged


def test_merge_doc_results_prefers_a_new_document_over_a_second_chunk():
    # A single document often supplies several chunks. Spending the block budget on
    # them buries a document the question actually needs: this is how the brief for
    # "Stripe API key leaked" never saw 015-emergency-secrets-rotation.
    def two_chunks(source: str) -> str:
        return "\n\n".join(
            format_doc_result(
                i + 1, "runbook", f"docs/runbooks/{source}.md", f"chunk{i} of {source}"
            )
            for i in range(2)
        )

    merged = _merge_doc_results([two_chunks("a-one"), two_chunks("b-two")], max_blocks=3)

    assert "chunk0 of a-one" in merged
    assert "chunk0 of b-two" in merged  # breadth before depth


def test_merge_doc_results_still_uses_leftover_budget_for_second_chunks():
    def two_chunks(source: str) -> str:
        return "\n\n".join(
            format_doc_result(
                i + 1, "runbook", f"docs/runbooks/{source}.md", f"chunk{i} of {source}"
            )
            for i in range(2)
        )

    merged = _merge_doc_results([two_chunks("a-one"), two_chunks("b-two")], max_blocks=6)
    for expected in ("chunk0 of a-one", "chunk0 of b-two", "chunk1 of a-one", "chunk1 of b-two"):
        assert expected in merged


def test_merge_doc_results_ranks_best_hits_first():
    results = [_result("q1-first", "q1-second"), _result("q2-first", "q2-second")]
    merged = _merge_doc_results(results)
    order = [merged.index(f"body of {s}") for s in ("q1-first", "q2-first", "q1-second")]
    assert order == sorted(order)


def test_merge_doc_results_caps_total_chars():
    one = _result("a-one")
    merged = _merge_doc_results([_result("a-one", "b-two")], max_chars=len(one) + 5)
    assert "body of a-one" in merged
    assert "body of b-two" not in merged


def test_merge_doc_results_keeps_citation_tags():
    # synthesize cites from these tags, so they must survive the merge intact.
    merged = _merge_doc_results([_result("001-checkout-504")])
    assert "Cite as: [001-checkout-504]" in merged


def test_merge_doc_results_handles_no_hits():
    assert _merge_doc_results(["No relevant documentation found."]) == ""
    assert _merge_doc_results([]) == ""


# --- keeping the retrieval evaluators able to see the documents --------------


def test_doc_tool_messages_are_readable_by_the_retrieval_evaluators():
    queries = ["checkout 504 runbook", "checkout mitigation"]
    results = [_result("001-checkout-504"), _result("002-payment-timeouts")]

    messages = _doc_tool_messages(queries, results)

    # This is the contract the eval harness depends on: retrieval_precision,
    # retrieval_recall and citation_validity all read ToolMessages, not state.
    assert extract_retrieved_sources(messages) == ["001-checkout-504", "002-payment-timeouts"]


def test_doc_tool_messages_pair_every_call_with_its_result():
    queries = ["q1", "q2"]
    messages = _doc_tool_messages(queries, [_result("a-one"), _result("b-two")])

    ai = messages[0]
    tool_msgs = messages[1:]
    # One AI message announcing both calls (what the UI renders as chips), then
    # one ToolMessage per call, with ids that match.
    assert [tc["name"] for tc in ai.tool_calls] == ["search_engineering_docs"] * 2
    assert [tc["args"]["query"] for tc in ai.tool_calls] == queries
    assert {tc["id"] for tc in ai.tool_calls} == {m.tool_call_id for m in tool_msgs}
    assert all(m.name == "search_engineering_docs" for m in tool_msgs)


def test_doc_tool_messages_empty_when_nothing_searched():
    assert _doc_tool_messages([], []) == []


# --- parallel execution ------------------------------------------------------


def test_search_docs_parallel_preserves_query_order():
    results = _search_docs_parallel(["a", "b", "c"], search=lambda q: f"result-{q}")
    assert results == ["result-a", "result-b", "result-c"]


def test_search_docs_parallel_actually_overlaps():
    started = threading.Barrier(3, timeout=5)

    def slow(query: str) -> str:
        started.wait()  # deadlocks unless all three run concurrently
        return query

    began = time.perf_counter()
    assert _search_docs_parallel(["a", "b", "c"], search=slow) == ["a", "b", "c"]
    assert time.perf_counter() - began < 5


def test_search_docs_parallel_survives_one_failing_search():
    def flaky(query: str) -> str:
        if query == "b":
            raise RuntimeError("chroma down")
        return f"ok-{query}"

    # A degraded search beats a failed turn, matching the tool's own error stance.
    results = _search_docs_parallel(["a", "b", "c"], search=flaky)
    assert results[0] == "ok-a"
    assert results[2] == "ok-c"
    assert "chroma down" in results[1] or results[1] == ""


def test_search_docs_parallel_no_queries():
    assert _search_docs_parallel([], search=lambda q: "x") == []


# --- async parallel execution ------------------------------------------------


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_asearch_docs_parallel_preserves_query_order():
    async def fake(query: str) -> str:
        return f"result-{query}"

    assert await _asearch_docs_parallel(["a", "b", "c"], search=fake) == [
        "result-a",
        "result-b",
        "result-c",
    ]


@pytest.mark.anyio
async def test_asearch_docs_parallel_overlaps_without_blocking_the_loop():
    running = 0
    peak = 0

    async def slow(query: str) -> str:
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await asyncio.sleep(0.05)
        running -= 1
        return query

    began = time.perf_counter()
    assert await _asearch_docs_parallel(["a", "b", "c"], search=slow) == ["a", "b", "c"]
    elapsed = time.perf_counter() - began

    assert peak == 3  # all three in flight at once
    assert elapsed < 0.12  # concurrent, not 3 x 0.05 serial


@pytest.mark.anyio
async def test_asearch_docs_parallel_survives_one_failing_search():
    async def flaky(query: str) -> str:
        if query == "b":
            raise RuntimeError("chroma down")
        return f"ok-{query}"

    results = await _asearch_docs_parallel(["a", "b", "c"], search=flaky)
    assert results[0] == "ok-a"
    assert results[2] == "ok-c"
    assert "chroma down" in results[1]


@pytest.mark.anyio
async def test_asearch_docs_parallel_no_queries():
    async def fake(query: str) -> str:
        return "x"

    assert await _asearch_docs_parallel([], search=fake) == []


# --- planner fallback --------------------------------------------------------


@pytest.mark.parametrize(
    "triage, expected_fragment",
    [
        (
            {"service_hint": "checkout-service", "symptoms_summary": "504 timeouts"},
            "checkout-service",
        ),
        ({"endpoint_hint": "/api/v1/checkout", "symptoms_summary": "504"}, "/api/v1/checkout"),
        ({}, "everything down"),
    ],
)
def test_fallback_doc_queries_use_triage_hints_then_user_text(triage, expected_fragment):
    queries = _fallback_doc_queries(triage, "everything down")
    assert queries
    assert any(expected_fragment in q for q in queries)


def test_fallback_doc_queries_are_sentences_not_bare_keywords():
    # The tool's docstring is explicit that two-word queries retrieve worse.
    queries = _fallback_doc_queries({"service_hint": "checkout-service"}, "504s")
    assert all(len(q.split()) >= 3 for q in queries)
