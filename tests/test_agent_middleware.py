"""Unit tests for context-management middleware wiring in the supervisor graph.

These do not call any LLM or need a corpus: `create_agent` is patched so we can
assert which middleware each ReAct agent is constructed with. The `general_agent`
(all tools) summarizes history; `structured_agent` clears stale tool results.

There are two ReAct agents, not three: the runbook step is a query planner plus a
parallel search, with no tool-calling loop to manage. See create_enterprise_copilot
in src/agent.py.
"""

from unittest.mock import MagicMock, patch

import pytest
from langchain.agents.middleware import ContextEditingMiddleware, SummarizationMiddleware

import src.agent as agent_mod


@pytest.fixture
def captured_agents(monkeypatch):
    """Build the graph with create_agent patched; return calls keyed by tool count."""
    # ChatOpenAI construction reads a key but makes no network call at init.
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-unused")
    calls = []

    def fake_create_agent(model, *, tools, system_prompt=None, middleware=(), **_kw):
        calls.append({"tools": tools, "middleware": list(middleware)})
        return MagicMock()

    with patch.object(agent_mod, "create_agent", fake_create_agent):
        agent_mod.create_enterprise_copilot()

    # tool counts are distinct: general=4, structured(sql)=3
    return {len(c["tools"]): c["middleware"] for c in calls}


def test_only_the_tool_calling_steps_are_react_agents(captured_agents):
    # The runbook step plans its searches in one structured call and runs them
    # directly, so it needs no agent loop and builds no third agent.
    assert set(captured_agents) == {4, 3}


def test_general_agent_uses_summarization(captured_agents):
    middleware = captured_agents[4]
    assert len(middleware) == 1
    assert isinstance(middleware[0], SummarizationMiddleware)


def test_structured_agent_uses_context_editing(captured_agents):
    middleware = captured_agents[3]
    assert len(middleware) == 1
    assert isinstance(middleware[0], ContextEditingMiddleware)


def test_summarization_honors_config(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-unused")
    monkeypatch.setenv("EAC_SUMMARIZATION_TRIGGER_TOKENS", "1234")
    monkeypatch.setenv("EAC_SUMMARIZATION_KEEP_MESSAGES", "7")
    captured = {}

    def fake_create_agent(model, *, tools, system_prompt=None, middleware=(), **_kw):
        if len(tools) == 4:
            captured["mw"] = middleware[0]
        return MagicMock()

    with patch.object(agent_mod, "create_agent", fake_create_agent):
        agent_mod.create_enterprise_copilot()

    mw = captured["mw"]
    assert mw.trigger == ("tokens", 1234)
    assert mw.keep == ("messages", 7)
