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
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage

from src.agent import PROMPT_INJECTION_MESSAGE
from src.api.app import _transcript
from src.api.observability import (
    GUARDRAIL_BLOCKS,
    JsonLogFormatter,
    _histogram_quantile,
    metrics_summary,
    record_guardrail_outcome,
    record_node_duration,
    record_time_to_first_token,
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
    def __init__(self, events, error: Exception | None = None, state_messages=None):
        self._events = events
        self._error = error
        self._state_messages = state_messages or []

    async def astream(self, inputs, run_config=None, stream_mode=None):
        for event in self._events:
            yield event
        if self._error is not None:
            raise self._error

    async def aget_state(self, run_config):
        from types import SimpleNamespace

        return SimpleNamespace(values={"messages": self._state_messages})


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


@pytest.mark.anyio
async def test_stream_times_each_node_it_completes():
    seen: list[tuple[str, float]] = []
    agent = FakeAgent(_canned_events())
    await _collect(
        chat_event_stream(agent, "q", "t-1", {}, on_node_complete=lambda n, s: seen.append((n, s)))
    )

    assert [name for name, _ in seen] == [
        "validate_input",
        "triage",
        "structured_agent",
        "synthesize",
    ]
    assert all(seconds >= 0 for _, seconds in seen)


@pytest.mark.anyio
async def test_stream_reports_time_to_first_token_once():
    seen: list[float] = []
    agent = FakeAgent(_canned_events())
    await _collect(chat_event_stream(agent, "q", "t-1", {}, on_first_token=seen.append))

    # Two user-facing token chunks ("Fin", "al"), but TTFT is a single observation.
    assert len(seen) == 1
    assert seen[0] >= 0


@pytest.mark.anyio
async def test_stream_skips_time_to_first_token_when_nothing_streams():
    # A declined turn emits no user-facing tokens, so there is no TTFT to record.
    seen: list[float] = []
    agent = FakeAgent([("updates", {"decline_node": {"mode": "out_of_scope"}})])
    await _collect(chat_event_stream(agent, "q", "t-1", {}, on_first_token=seen.append))
    assert seen == []


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


def test_histogram_quantile_interpolates_within_bucket():
    # 10 observations: 5 in <=0.1, 3 more by <=0.5, 1 more by <=1.0, 1 in +Inf.
    buckets = [(0.1, 5.0), (0.5, 8.0), (1.0, 9.0), (float("inf"), 10.0)]
    # p50 (rank 5) lands at the top of the first bucket: 0 + 0.1 * (5/5).
    assert _histogram_quantile(buckets, 0.50) == pytest.approx(0.1)
    # p95 (rank 9.5) falls in the +Inf bucket, so it clamps to the last finite le.
    assert _histogram_quantile(buckets, 0.95) == 1.0


def test_histogram_quantile_empty_is_none():
    assert _histogram_quantile([], 0.5) is None
    assert _histogram_quantile([(float("inf"), 0.0)], 0.5) is None


def test_metrics_summary_shape():
    summary = metrics_summary()
    assert set(summary) == {
        "requests",
        "chat_latency",
        "overall_latency",
        "node_latency",
        "time_to_first_token",
        "guardrail_blocks",
    }
    assert isinstance(summary["requests"]["total"], int)
    assert isinstance(summary["requests"]["by_endpoint"], list)
    assert isinstance(summary["guardrail_blocks"], dict)


def test_node_latency_ranks_the_slowest_node_first():
    # The point of the section: read the top row to see where a turn spends its time.
    record_node_duration("triage", 1.0)
    record_node_duration("runbook_agent", 5.0)
    record_node_duration("runbook_agent", 7.0)

    rows = {r["node"]: r for r in metrics_summary()["node_latency"]}
    assert rows["runbook_agent"]["count"] == 2
    assert rows["runbook_agent"]["avg_seconds"] == pytest.approx(6.0)
    assert rows["runbook_agent"]["total_seconds"] == pytest.approx(12.0)

    ordered = [r["node"] for r in metrics_summary()["node_latency"]]
    assert ordered.index("runbook_agent") < ordered.index("triage")


def test_time_to_first_token_summary_reports_percentiles():
    record_time_to_first_token(2.0)
    ttft = metrics_summary()["time_to_first_token"]
    assert ttft["count"] >= 1
    assert ttft["avg_seconds"] > 0
    assert ttft["p95_seconds"] is not None


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


def test_root_serves_chat_ui(client):
    root = client.get("/")
    assert root.status_code == 200
    assert "X-Request-ID" in root.headers
    assert "text/html" in root.headers["content-type"]
    assert "Enterprise Architecture Copilot" in root.text


def test_static_assets_served(client):
    for path in ("/app.js", "/style.css"):
        resp = client.get(path)
        assert resp.status_code == 200, path


def test_metrics_endpoint(client):
    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert "http_request" in metrics.text


def test_metrics_summary_endpoint(client):
    # /healthz is instrumented (unlike /metrics*), so at least one request is counted.
    client.get("/healthz")
    resp = client.get("/metrics/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {
        "requests",
        "chat_latency",
        "overall_latency",
        "node_latency",
        "time_to_first_token",
        "guardrail_blocks",
    }
    assert body["requests"]["total"] >= 1


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


def test_chat_frames_end_with_a_blank_line_the_ui_can_split_on(client):
    """Regression: the UI never rendered anything because of frame separators.

    sse-starlette defaults to `\\r\\n` line endings, so frames end with
    `\\r\\n\\r\\n`, which contains no `\\n\\n`. The browser client splits the stream
    on a blank line, found no frame boundary, and dropped every event including
    `done`, leaving an empty chat bubble while the server streamed normally.
    """
    client.app.state.agent = FakeAgent(_canned_events())
    body = client.post("/chat", json={"message": "504s on checkout"}).text

    frames = [f for f in body.split("\n\n") if f.strip()]
    assert len(frames) > 1, "no frame boundary the UI parser can find"
    assert all(f.lstrip().startswith("event: ") for f in frames)
    assert frames[-1].lstrip().startswith("event: done")


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


# --- transcript + thread history ---------------------------------------------------


def test_transcript_keeps_user_and_final_answers_only():
    messages = [
        HumanMessage(content="who owns checkout-service?"),
        AIMessage(content="", tool_calls=[{"name": "query_sql_database", "args": {}, "id": "t1"}]),
        AIMessage(content="Team Alpha owns checkout-service."),
        HumanMessage(content="and the runbook?"),
        AIMessage(content="RB-001 covers 504s."),
    ]
    assert _transcript(messages) == [
        {"role": "user", "content": "who owns checkout-service?"},
        {"role": "assistant", "content": "Team Alpha owns checkout-service."},
        {"role": "user", "content": "and the runbook?"},
        {"role": "assistant", "content": "RB-001 covers 504s."},
    ]


def test_thread_messages_endpoint_returns_transcript(client):
    client.app.state.agent = FakeAgent(
        [],
        state_messages=[
            HumanMessage(content="hi"),
            AIMessage(content="hello, ask about PayLane"),
        ],
    )
    response = client.get("/threads/t-77/messages")
    assert response.status_code == 200
    body = response.json()
    assert body["thread_id"] == "t-77"
    assert body["messages"] == [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello, ask about PayLane"},
    ]
