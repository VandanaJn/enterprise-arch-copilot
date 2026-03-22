"""Unit tests for incident routing helpers (TDD: pure logic, no LLM)."""

from src.incident_workflow import (
    route_target_for_mode,
    latest_user_text,
    extract_final_assistant_text,
)
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage


def test_route_target_for_mode_incident():
    assert route_target_for_mode("incident") == "structured_agent"


def test_route_target_for_mode_general():
    assert route_target_for_mode("general") == "general_agent"


def test_route_target_for_mode_default_none():
    assert route_target_for_mode(None) == "general_agent"


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
