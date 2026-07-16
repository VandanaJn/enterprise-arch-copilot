"""Tests for the FastAPI service layer.

Pure tests cover the SSE event builders, the stream adapter (with a fake agent),
the rate limiter (injected clock), and the observability helpers. TestClient tests
exercise the HTTP surface without any LLM: the compiled graph in app.state is
swapped for a fake after startup, and the injection-detector warm-up is disabled
via env so no model download happens.
"""

from __future__ import annotations

import json
import logging
import os

import pytest
from langchain_core.messages import AIMessage, AIMessageChunk

from src.agent import PROMPT_INJECTION_MESSAGE
from src.api.observability import (
    GUARDRAIL_BLOCKS,
    JsonLogFormatter,
    record_guardrail_outcome,
)
from src.api.rate_limit import SlidingWindowLimiter
from src.api.sse import (
    chat_event_stream,
    chunk_text,
    done_event,
    error_event,
    is_user_facing_token,
    token_event,
)

# --- SSE event builders -----------------------------------------------------------


def test_event_payloads_are_json():
    ev = token_event("hi")
    assert ev["event"] == "token"
    assert json.loads(ev["data"]) == {"text": "hi"}

    ev = done_event("answer", "t-1", run_id="r-9")
    assert json.loads(ev["data"]) == {"text": "answer", "thread_id": "t-1", "run_id": "r-9"}

    ev = done_event("answer", "t-1")
    assert "run_id" not in json.loads(ev["data"])

    ev = error_event("boom")
    assert ev["event"] == "error"


def test_is_user_facing_token_filters_nodes():
    assert is_user_facing_token({"langgraph_node": "synthesize"})
    assert is_user_facing_token({"langgraph_checkpoint_ns": "general_agent:abc|model"})
    assert not is_user_facing_token({"langgraph_node": "triage"})
    assert not is_user_facing_token({"langgraph_checkpoint_ns": "runbook_agent:abc"})
    assert not is_user_facing_token({})


def test_chunk_text_handles_block_content():
    assert chunk_text(AIMessageChunk(content="plain")) == "plain"
    blocks = AIMessageChunk(content=[{"type": "text", "text": "a"}, {"type": "text", "text": "b"}])
    assert chunk_text(blocks) == "ab"


# --- chat_event_stream with a fake agent ------------------------------------------


class FakeAgent:
    def __init__(self, events, error: Exception | None = None):
        self._events = events
        self._error = error

    async def astream(self, inputs, run_config=None, stream_mode=None):
        for event in self._events:
            yield event
        if self._error is not None:
            raise self._error


def _canned_events():
    return [
        ("updates", {"validate_input": {}}),
        ("updates", {"triage": {"mode": "incident", "triage": {"mode": "incident"}}}),
        (
            "messages",
            (AIMessageChunk(content="internal"), {"langgraph_node": "triage"}),
        ),
        (
            "updates",
            {
                "structured_agent": {
                    "messages": [
                        AIMessage(
                            content="",
                            tool_calls=[
                                {
                                    "name": "query_sql_database",
                                    "args": {"query": "SELECT 1"},
                                    "id": "tc1",
                                }
                            ],
                        )
                    ]
                }
            },
        ),
        ("messages", (AIMessageChunk(content="Fin"), {"langgraph_node": "synthesize"})),
        ("messages", (AIMessageChunk(content="al"), {"langgraph_node": "synthesize"})),
        ("updates", {"synthesize": {"messages": [AIMessage(content="Final brief")]}}),
    ]


async def _collect(stream):
    return [event async for event in stream]


@pytest.mark.anyio
async def test_stream_filters_tokens_and_ends_with_done():
    agent = FakeAgent(_canned_events())
    events = await _collect(chat_event_stream(agent, "504s on checkout", "t-42", {}))

    kinds = [e["event"] for e in events]
    assert kinds[-1] == "done"
    assert "error" not in kinds

    tokens = [json.loads(e["data"])["text"] for e in events if e["event"] == "token"]
    assert tokens == ["Fin", "al"]  # triage tokens never leak

    tool_calls = [json.loads(e["data"]) for e in events if e["event"] == "tool_call"]
    assert tool_calls == [{"name": "query_sql_database", "args": {"query": "SELECT 1"}}]

    done = json.loads(events[-1]["data"])
    assert done["text"] == "Final brief"
    assert done["thread_id"] == "t-42"


@pytest.mark.anyio
async def test_stream_emits_error_event_on_failure():
    agent = FakeAgent([("updates", {"validate_input": {}})], error=RuntimeError("kaput"))
    events = await _collect(chat_event_stream(agent, "q", "t-1", {}))
    assert events[-1]["event"] == "error"
    assert "kaput" in json.loads(events[-1]["data"])["message"]
    assert not any(e["event"] == "done" for e in events)


@pytest.mark.anyio
async def test_stream_fires_on_complete_hook():
    seen = {}

    def hook(mode, messages):
        seen["mode"] = mode
        seen["n"] = len(messages)

    agent = FakeAgent(_canned_events())
    await _collect(chat_event_stream(agent, "q", "t-1", {}, on_complete=hook))
    assert seen["mode"] == "incident"
    assert seen["n"] >= 3


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def _reset_sse_appstatus():
    # sse-starlette caches an asyncio.Event on AppStatus at class level, bound to
    # the first event loop it sees. Each TestClient runs its own loop, so without a
    # reset the second SSE test reuses a stale event and raises a cross-loop error.
    from sse_starlette.sse import AppStatus

    AppStatus.should_exit_event = None
    yield
    AppStatus.should_exit_event = None


# --- rate limiter ------------------------------------------------------------------


def test_rate_limiter_sliding_window():
    clock = {"t": 0.0}
    limiter = SlidingWindowLimiter(window_seconds=60, clock=lambda: clock["t"])

    assert limiter.allow("ip1", limit=2)
    assert limiter.allow("ip1", limit=2)
    assert not limiter.allow("ip1", limit=2)
    assert limiter.allow("ip2", limit=2)  # other clients unaffected

    clock["t"] = 61.0  # window rolls over
    assert limiter.allow("ip1", limit=2)


def test_rate_limiter_disabled_at_zero():
    limiter = SlidingWindowLimiter()
    assert all(limiter.allow("ip1", limit=0) for _ in range(100))


# --- observability -----------------------------------------------------------------


def test_json_log_formatter_emits_parseable_json():
    record = logging.LogRecord("eac.test", logging.INFO, __file__, 1, "hello %s", ("world",), None)
    record.request_id = "req-1"
    entry = json.loads(JsonLogFormatter().format(record))
    assert entry["message"] == "hello world"
    assert entry["level"] == "INFO"
    assert entry["request_id"] == "req-1"


def _counter_value(guardrail: str) -> float:
    return GUARDRAIL_BLOCKS.labels(guardrail=guardrail)._value.get()


def test_guardrail_counter_prompt_injection():
    before = _counter_value("prompt-injection")
    record_guardrail_outcome("rejected", [AIMessage(content=PROMPT_INJECTION_MESSAGE)])
    assert _counter_value("prompt-injection") == before + 1


def test_guardrail_counter_input_validation():
    before = _counter_value("input-validation")
    record_guardrail_outcome("rejected", [AIMessage(content="Your message is too long")])
    assert _counter_value("input-validation") == before + 1


# --- HTTP surface (TestClient, no LLM) ---------------------------------------------


@pytest.fixture
def api_app(monkeypatch):
    # Function-scoped: each test gets a fresh app so the rate limiter and any
    # event-loop-bound objects don't leak across TestClient loops.
    monkeypatch.setenv("EAC_WARM_INJECTION_DETECTOR", "0")
    if not os.environ.get("OPENAI_API_KEY"):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-used")

    from src.api.app import create_app

    return create_app()


@pytest.fixture
def client(api_app):
    from fastapi.testclient import TestClient

    with TestClient(api_app) as test_client:
        yield test_client


def test_healthz_unhealthy_without_assets(client):
    response = client.get("/healthz")
    assert response.status_code == 503
    assert response.json()["reasons"]


def test_healthz_ok_with_assets(client, tmp_path, monkeypatch):
    db = tmp_path / "engineering_data.db"
    db.write_text("")
    chroma = tmp_path / "chroma_db"
    chroma.mkdir()
    monkeypatch.setenv("EAC_DB_FILE", str(db))
    monkeypatch.setenv("EAC_CHROMA_DIR", str(chroma))

    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_root_and_metrics_and_request_id(client):
    root = client.get("/")
    assert root.status_code == 200
    assert "X-Request-ID" in root.headers

    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert "http_request" in metrics.text


def test_chat_streams_sse_and_round_trips_thread_id(client):
    client.app.state.agent = FakeAgent(_canned_events())
    response = client.post("/chat", json={"message": "504s on checkout", "thread_id": "t-abc"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    body = response.text
    assert "event: token" in body
    assert "event: tool_call" in body
    assert body.rstrip().split("event: ")[-1].startswith("done")
    assert '"thread_id": "t-abc"' in body


def test_chat_mints_thread_id_when_absent(client):
    client.app.state.agent = FakeAgent(_canned_events())
    response = client.post("/chat", json={"message": "hello"})
    done_line = [line for line in response.text.splitlines() if '"thread_id"' in line][-1]
    assert json.loads(done_line.split("data: ", 1)[1])["thread_id"]


def test_chat_rate_limited(client, monkeypatch):
    monkeypatch.setenv("EAC_RATE_LIMIT_PER_MIN", "1")
    client.app.state.agent = FakeAgent(_canned_events())
    first = client.post("/chat", json={"message": "one"})
    second = client.post("/chat", json={"message": "two"})
    assert first.status_code == 200
    assert second.status_code == 429
