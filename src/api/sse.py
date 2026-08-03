"""SSE event construction and the chat event stream.

Event builders are pure (dict in, dict out) so they unit-test without a server.
`chat_event_stream` adapts `agent.astream(..., stream_mode=["updates", "messages"])`
into a filtered sequence of SSE events:

- `token`: answer tokens from user-facing nodes only (`synthesize` and the
  `general_agent` subgraph). Internal triage / sub-agent tokens never leak.
- `node`: a graph node completed (UI affordance).
- `tool_call`: a tool was invoked (name + args, rendered as chips in a UI).
- `done`: terminal; carries the full final answer text and the thread_id.
- `error`: terminal; the stream failed.

All `data` payloads are JSON.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import AsyncIterator, Callable
from typing import Any

from langchain_core.messages import HumanMessage

from src.incident_workflow import extract_final_assistant_text

logger = logging.getLogger(__name__)

# Nodes whose LLM tokens are the user-facing answer. `synthesize` writes the incident
# brief; the general path streams from inside the `general_agent` subgraph, which shows
# up in metadata as a checkpoint namespace prefixed with the node name.
TOKEN_NODES = ("synthesize",)
GENERAL_AGENT_NS_PREFIX = "general_agent"


def _event(name: str, payload: dict) -> dict:
    return {"event": name, "data": json.dumps(payload, ensure_ascii=False)}


def token_event(text: str) -> dict:
    return _event("token", {"text": text})


def node_event(name: str) -> dict:
    return _event("node", {"name": name})


def tool_call_event(name: str, args: dict) -> dict:
    return _event("tool_call", {"name": name, "args": args})


def done_event(text: str, thread_id: str, run_id: str | None = None) -> dict:
    payload: dict = {"text": text, "thread_id": thread_id}
    if run_id:
        payload["run_id"] = run_id
    return _event("done", payload)


def error_event(message: str) -> dict:
    return _event("error", {"message": message})


def is_user_facing_token(metadata: dict) -> bool:
    """True when a streamed LLM chunk belongs to a node whose output the user sees."""
    if metadata.get("langgraph_node") in TOKEN_NODES:
        return True
    ns = metadata.get("langgraph_checkpoint_ns") or ""
    return ns.startswith(GENERAL_AGENT_NS_PREFIX)


def chunk_text(chunk: Any) -> str:
    """Plain text of a streamed message chunk (handles list-of-blocks content)."""
    content = getattr(chunk, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "".join(parts)
    return ""


def _safe_hook(hook: Callable | None, *args) -> None:
    """Call an observability hook; a metrics failure must never break the stream."""
    if hook is None:
        return
    try:
        hook(*args)
    except Exception:
        logger.exception("stream observability hook failed")


def _is_answer_chunk(chunk: Any) -> bool:
    """AI chunks only, and not the tool-call-argument chunks a ReAct step streams."""
    chunk_type = getattr(chunk, "type", "")
    if chunk_type not in ("ai", "AIMessageChunk"):
        return False
    return not getattr(chunk, "tool_call_chunks", None)


async def chat_event_stream(
    agent: Any,
    message: str,
    thread_id: str,
    run_config: dict,
    on_complete: Callable[[str, list], None] | None = None,
    run_id: str | None = None,
    on_node_complete: Callable[[str, float], None] | None = None,
    on_first_token: Callable[[float], None] | None = None,
) -> AsyncIterator[dict]:
    """Yield SSE events for one chat turn.

    `on_complete(final_mode, all_messages)` fires before the done event; the
    observability layer uses it to record guardrail outcomes without this module
    depending on metrics.

    `on_node_complete(node, seconds)` and `on_first_token(seconds)` are the latency
    hooks, injected the same way. LangGraph emits an `updates` payload when a node
    finishes, so the gap since the previous update is that node's wall clock
    (graph overhead included), enough to attribute a slow turn to a step without
    instrumenting the graph itself.
    """
    inputs = {"messages": [HumanMessage(content=message)]}
    all_messages: list = list(inputs["messages"])
    seen_msg_ids: set[str] = set()
    final_mode = ""
    started = time.perf_counter()
    node_started = started
    first_token_seen = False

    try:
        async for stream_mode, payload in agent.astream(
            inputs, run_config, stream_mode=["updates", "messages"]
        ):
            if stream_mode == "messages":
                chunk, metadata = payload
                if not _is_answer_chunk(chunk) or not is_user_facing_token(metadata or {}):
                    continue
                text = chunk_text(chunk)
                if text:
                    if not first_token_seen:
                        first_token_seen = True
                        _safe_hook(on_first_token, time.perf_counter() - started)
                    yield token_event(text)
            elif stream_mode == "updates":
                for node_name, update in (payload or {}).items():
                    now = time.perf_counter()
                    _safe_hook(on_node_complete, node_name, now - node_started)
                    node_started = now
                    yield node_event(node_name)
                    if not isinstance(update, dict):
                        continue
                    if update.get("mode"):
                        final_mode = update["mode"]
                    for msg in update.get("messages") or []:
                        msg_id = getattr(msg, "id", None)
                        if msg_id and msg_id in seen_msg_ids:
                            continue
                        if msg_id:
                            seen_msg_ids.add(msg_id)
                        all_messages.append(msg)
                        if getattr(msg, "type", "") == "ai":
                            for tc in getattr(msg, "tool_calls", None) or []:
                                yield tool_call_event(tc.get("name", ""), tc.get("args", {}))
    except Exception as exc:
        logger.exception("chat stream failed (thread_id=%s)", thread_id)
        yield error_event(str(exc))
        return

    final_text = extract_final_assistant_text(all_messages)
    if on_complete is not None:
        try:
            on_complete(final_mode, all_messages)
        except Exception:
            logger.exception("on_complete hook failed")
    yield done_event(final_text, thread_id, run_id=run_id)
