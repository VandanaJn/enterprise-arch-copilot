"""Integration tests for the LangGraph supervisor agent.

These tests need a populated tests/test_data/ corpus (docs + SQLite + chroma_db).
The session-scoped `built_test_data` fixture in conftest.py provides exactly
that, isolated from the developer's real data directories.
"""

import pytest
from langchain_core.messages import HumanMessage

from src.agent import (
    create_enterprise_copilot,
    query_sql_database,
    search_engineering_docs,
)


def _collect_tool_calls_from_stream(graph, inputs):
    """Gather tool names from any node update in the graph stream."""
    tool_calls = []
    for chunk in graph.stream(inputs):
        for _node_name, node_data in chunk.items():
            if not isinstance(node_data, dict) or "messages" not in node_data:
                continue
            for msg in node_data["messages"]:
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        tool_calls.append(tc["name"])
                elif hasattr(msg, "name") and msg.name:
                    tool_calls.append(msg.name)
    return tool_calls


@pytest.mark.integration
def test_vector_tool_execution(built_test_data):
    result = search_engineering_docs.invoke(
        {"query": "What was the rationale behind migrating our payment gateway to the new AWS architecture?"}
    )
    
    result_lower = result.lower()
    assert "elasticity" in result_lower or "auto-scaling" in result_lower, (
        f"Expected 'elasticity' or 'auto-scaling' in result, got:\n{result}"
    )


@pytest.mark.integration
def test_sql_tool_execution(built_test_data):
    result = query_sql_database.invoke(
        {"query": "SELECT owner_team FROM service_catalog WHERE name = 'user-profile-service'"}
    )
    assert "Team Beta" in result


@pytest.mark.integration
def test_agent_routes_to_vector(built_test_data):
    agent = create_enterprise_copilot()
    inputs = {"messages": [HumanMessage(content="Why did we start using Kafka?")]}
    tool_calls = _collect_tool_calls_from_stream(agent, inputs)
    assert "search_engineering_docs" in tool_calls


@pytest.mark.integration
def test_agent_routes_to_sql(built_test_data):
    agent = create_enterprise_copilot()
    inputs = {"messages": [HumanMessage(content="What version is the order-service currently on?")]}
    tool_calls = _collect_tool_calls_from_stream(agent, inputs)
    assert any("sql" in tool.lower() for tool in tool_calls)


@pytest.mark.integration
def test_agent_hybrid_search(built_test_data):
    agent = create_enterprise_copilot()
    content = "The /api/v1/checkout endpoint is failing with a 504. Who owns it and is there a runbook for it?"
    inputs = {"messages": [HumanMessage(content=content)]}
    tool_calls = [t.lower() for t in _collect_tool_calls_from_stream(agent, inputs)]
    assert any("sql" in tool for tool in tool_calls)
    assert "search_engineering_docs" in tool_calls

    result = agent.invoke(inputs)
    final_answer = result["messages"][-1].content.lower()
    assert "alpha" in final_answer
    assert "mitigation" in final_answer or "runbook" in final_answer
