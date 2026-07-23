"""Unit tests for supersession-aware retrieval.

Pure tests: no vector store, no embeddings, no API key. The re-ranker takes a
`fetch_adr` callable, so the store lookup is injected as a plain dict lookup here
and as a filtered similarity search in production.
"""

from __future__ import annotations

from langchain_core.documents import Document

from src.agent import (
    _adr_ids_in_query,
    _pin_referenced_adrs,
    _prefer_current_adrs,
    _supersession_note,
)

# --- Fixtures as plain documents ----------------------------------------------

ADR_001 = Document(
    page_content="We adopt RabbitMQ for inter-service messaging.",
    metadata={
        "source": "docs/adrs/001-rabbitmq-inter-service-messaging.md",
        "document_type": "adr",
        "adr_id": "ADR-001",
        "superseded_by": "ADR-002",
    },
)
ADR_002 = Document(
    page_content="We adopt Kafka for event streaming.",
    metadata={
        "source": "docs/adrs/002-adopt-kafka-event-streaming.md",
        "document_type": "adr",
        "adr_id": "ADR-002",
        "supersedes": "ADR-001",
    },
)
RUNBOOK = Document(
    page_content="Steps to drain a Kafka consumer group.",
    metadata={
        "source": "docs/runbooks/004-kafka-consumer-lag-spike.md",
        "document_type": "runbook",
    },
)


def _fetcher(*docs: Document):
    """fetch_adr callable backed by an in-memory index, recording its calls."""
    index = {d.metadata["adr_id"]: d for d in docs}
    calls: list[str] = []

    def fetch(adr_id: str) -> Document | None:
        calls.append(adr_id)
        return index.get(adr_id)

    fetch.calls = calls  # type: ignore[attr-defined]
    return fetch


def _sources(docs: list[Document]) -> list[str]:
    return [d.metadata.get("source", "") for d in docs]


# --- _prefer_current_adrs -----------------------------------------------------


def test_superseding_adr_is_fetched_and_ranked_first():
    fetch = _fetcher(ADR_002)
    result = _prefer_current_adrs([ADR_001, RUNBOOK], fetch)
    assert _sources(result) == _sources([ADR_002, ADR_001, RUNBOOK])


def test_superseded_adr_is_kept_not_dropped():
    """Questions like "what did we use before Kafka?" still need the old ADR."""
    result = _prefer_current_adrs([ADR_001], _fetcher(ADR_002))
    assert ADR_001 in result


def test_documents_without_supersession_metadata_are_untouched():
    fetch = _fetcher(ADR_002)
    result = _prefer_current_adrs([RUNBOOK, ADR_002], fetch)
    assert result == [RUNBOOK, ADR_002]
    assert fetch.calls == []


def test_already_retrieved_superseding_adr_is_reordered_without_a_lookup():
    fetch = _fetcher(ADR_002)
    result = _prefer_current_adrs([ADR_001, ADR_002], fetch)
    assert _sources(result) == _sources([ADR_002, ADR_001])
    assert fetch.calls == []


def test_no_duplicates_when_the_superseding_adr_appears_twice():
    result = _prefer_current_adrs([ADR_001, ADR_002], _fetcher(ADR_002))
    assert len(result) == 2


def test_missing_superseding_adr_leaves_results_unchanged():
    result = _prefer_current_adrs([ADR_001], _fetcher())
    assert result == [ADR_001]


def test_lookup_failure_is_swallowed_and_results_survive():
    def boom(adr_id: str) -> Document | None:
        raise RuntimeError("chroma is down")

    assert _prefer_current_adrs([ADR_001], boom) == [ADR_001]


def test_supersession_chain_resolves_to_the_current_adr():
    a = Document(page_content="A", metadata={"adr_id": "ADR-A", "superseded_by": "ADR-B"})
    b = Document(page_content="B", metadata={"adr_id": "ADR-B", "superseded_by": "ADR-C"})
    c = Document(page_content="C", metadata={"adr_id": "ADR-C"})
    result = _prefer_current_adrs([a], _fetcher(a, b, c))
    assert result[0] is c
    assert a in result


def test_supersession_cycle_terminates():
    a = Document(page_content="A", metadata={"adr_id": "ADR-A", "superseded_by": "ADR-B"})
    b = Document(page_content="B", metadata={"adr_id": "ADR-B", "superseded_by": "ADR-A"})
    result = _prefer_current_adrs([a], _fetcher(a, b))
    assert a in result


def test_lookups_are_capped():
    """Bounds the extra vector-store calls one tool invocation can trigger."""
    docs = [
        Document(
            page_content=str(n),
            metadata={"adr_id": f"ADR-{n:03d}", "superseded_by": f"ADR-{n + 100:03d}"},
        )
        for n in (1, 2, 3)
    ]
    fetch = _fetcher()
    _prefer_current_adrs(docs, fetch, max_lookups=2)
    assert len(fetch.calls) == 2


def test_empty_results_are_handled():
    assert _prefer_current_adrs([], _fetcher()) == []


# --- _adr_ids_in_query --------------------------------------------------------


def test_query_naming_an_adr_yields_its_id():
    assert _adr_ids_in_query("Is ADR-001 still in effect?") == ["ADR-001"]


def test_adr_reference_is_matched_loosely_and_normalized():
    assert _adr_ids_in_query("what does adr 2 supersede?") == ["ADR-002"]


def test_repeated_references_are_de_duplicated_in_order():
    assert _adr_ids_in_query("Does ADR-002 replace ADR-001 or ADR-2?") == ["ADR-002", "ADR-001"]


def test_query_without_an_adr_reference_yields_nothing():
    assert _adr_ids_in_query("Are we still using RabbitMQ?") == []


def test_other_document_ids_are_not_treated_as_adrs():
    assert _adr_ids_in_query("see RB-004 and PM-2024-001") == []


# --- _pin_referenced_adrs -----------------------------------------------------


def test_adr_named_in_the_query_is_fetched_and_pinned_first():
    """Cosine search misses bare ids like "ADR-001"; the metadata index doesn't."""
    fetch = _fetcher(ADR_001)
    result = _pin_referenced_adrs([RUNBOOK], "Is ADR-001 still in effect?", fetch)
    assert _sources(result) == _sources([ADR_001, RUNBOOK])
    assert fetch.calls == ["ADR-001"]


def test_already_retrieved_adr_is_not_fetched_again():
    fetch = _fetcher(ADR_001)
    result = _pin_referenced_adrs([ADR_001], "Is ADR-001 still in effect?", fetch)
    assert result == [ADR_001]
    assert fetch.calls == []


def test_query_without_an_adr_reference_triggers_no_lookup():
    fetch = _fetcher(ADR_001)
    assert _pin_referenced_adrs([RUNBOOK], "why did checkout 504?", fetch) == [RUNBOOK]
    assert fetch.calls == []


def test_unknown_adr_id_leaves_results_unchanged():
    assert _pin_referenced_adrs([RUNBOOK], "what about ADR-999?", _fetcher()) == [RUNBOOK]


def test_pin_lookup_failure_is_swallowed():
    def boom(adr_id: str) -> Document | None:
        raise RuntimeError("chroma is down")

    assert _pin_referenced_adrs([RUNBOOK], "Is ADR-001 still in effect?", boom) == [RUNBOOK]


def test_pin_lookups_are_capped():
    fetch = _fetcher()
    _pin_referenced_adrs([], "compare ADR-001, ADR-002 and ADR-003", fetch, max_lookups=2)
    assert len(fetch.calls) == 2


# --- _supersession_note -------------------------------------------------------


def test_note_flags_a_superseded_adr():
    assert _supersession_note(ADR_001.metadata) == "Status: superseded by ADR-002"


def test_note_marks_the_current_adr_as_authoritative():
    assert _supersession_note(ADR_002.metadata) == "Status: current; supersedes ADR-001"


def test_note_is_absent_for_documents_without_supersession_metadata():
    assert _supersession_note(RUNBOOK.metadata) is None
