"""Unit tests for incident routing helpers (TDD: pure logic, no LLM)."""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from src.incident_workflow import (
    extract_final_assistant_text,
    latest_user_text,
    route_target_for_mode,
    trim_history,
)


def test_route_target_for_mode_incident():
    assert route_target_for_mode("incident") == "structured_agent"


def test_route_target_for_mode_general():
    assert route_target_for_mode("general") == "general_agent"


def test_route_target_for_mode_default_none():
    assert route_target_for_mode(None) == "general_agent"


def test_route_target_for_mode_out_of_scope():
    assert route_target_for_mode("out_of_scope") == "decline_node"


def test_latest_user_text_finds_last_human():
    msgs = [
        HumanMessage(content="first"),
        AIMessage(content="reply"),
        HumanMessage(content="second"),
    ]
    assert latest_user_text(msgs) == "second"


def test_latest_user_text_empty():
    assert latest_user_text([]) == ""


def test_extract_final_assistant_text_prefers_last_ai_without_tools():
    msgs = [
        HumanMessage(content="hi"),
        AIMessage(content="calling", tool_calls=[{"name": "x", "args": {}, "id": "1"}]),
        ToolMessage(content="result", tool_call_id="1"),
        AIMessage(content="final answer"),
    ]
    assert extract_final_assistant_text(msgs) == "final answer"


def test_extract_final_assistant_text_skips_tool_only_ai():
    msgs = [
        HumanMessage(content="hi"),
        AIMessage(content="x", tool_calls=[{"name": "t", "args": {}, "id": "1"}]),
    ]
    assert extract_final_assistant_text(msgs) == ""


def test_trim_history_returns_all_when_within_limit():
    msgs = [HumanMessage(content="a"), AIMessage(content="b")]
    assert trim_history(msgs, 20) == msgs


def test_trim_history_zero_limit_is_noop():
    msgs = [HumanMessage(content="a"), AIMessage(content="b")]
    assert trim_history(msgs, 0) == msgs


def test_trim_history_keeps_recent_and_starts_on_human():
    # Two clean turns; trimming to a small window keeps the most recent turn and
    # starts on a human message (no orphan assistant/tool messages).
    msgs = [
        HumanMessage(content="turn 1"),
        AIMessage(content="answer 1"),
        HumanMessage(content="turn 2"),
        AIMessage(content="answer 2"),
    ]
    trimmed = trim_history(msgs, 2)
    assert trimmed[0].type == "human"
    assert trimmed[-1].content == "answer 2"
    assert len(trimmed) <= 3  # window may include the human boundary


def test_trim_history_does_not_lead_with_tool_message():
    msgs = [
        HumanMessage(content="q"),
        AIMessage(content="", tool_calls=[{"name": "t", "args": {}, "id": "1"}]),
        ToolMessage(content="tool result", tool_call_id="1"),
        AIMessage(content="final"),
        HumanMessage(content="followup"),
        AIMessage(content="final 2"),
    ]
    trimmed = trim_history(msgs, 3)
    assert trimmed[0].type == "human"
