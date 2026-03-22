import pytest
from langchain_core.messages import HumanMessage
# Note: These imports will fail initially in TDD because src.agent isn't built yet
from src.agent import search_engineering_docs, query_sql_database, create_enterprise_copilot, close_connections
from src.generate_mock_data import generate_structured_data, generate_unstructured_data, create_directories

@pytest.fixture(scope="module", autouse=True)
def setup_agent_test_data():
    """Ensure mock data exists for agent tests."""
    create_directories()
    generate_structured_data()
    generate_unstructured_data()
    yield
    # No teardown here, rely on session teardown in tests/conftest.py


@pytest.mark.integration
def test_vector_tool_execution():
    """Test that the unstructured search tool returns chunks from ChromaDB."""
    # Query related to ADR 002
    result = search_engineering_docs.invoke({"query": "What was the rationale behind migrating our payment gateway to the new AWS architecture?"})
    
    # We expect the text to contain the rationale mentioned in our mock data
    assert "elasticity" in result.lower() or "auto-scaling" in result.lower()


@pytest.mark.integration
def test_sql_tool_execution():
    """Test that the structured search tool executes queries against engineering_data.db."""
    # Query for the user profile service
    result = query_sql_database.invoke({"query": "SELECT owner_team FROM service_catalog WHERE name = 'user-profile-service'"})
    
    # We expect the tool to run syntax that returns the owner from SQLite
    assert "Team Beta" in result


@pytest.mark.integration
def test_agent_routes_to_vector():
    """Test that the LangGraph agent routes unstructured conceptually queries to Vector DB."""
    agent = create_enterprise_copilot()
    
    inputs = {"messages": [HumanMessage(content="Why did we start using Kafka?")]}
    
    # Track which tools were called
    tool_calls = []
    for chunk in agent.stream(inputs):
        # In our new StateGraph, chunks are keyed by node name ('agent')
        if "agent" in chunk:
            for msg in chunk["agent"]["messages"]:
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        tool_calls.append(tc["name"])
                elif hasattr(msg, "name") and msg.name:
                    # In case of ToolMessage
                    tool_calls.append(msg.name)
                
    # Assert the agent decided to use our vector search tool
    assert "search_engineering_docs" in tool_calls

@pytest.mark.integration
def test_agent_routes_to_sql():
    """Test that the LangGraph agent routes factual metadata queries to the SQLite DB."""
    agent = create_enterprise_copilot()
    
    inputs = {"messages": [HumanMessage(content="What version is the order-service currently on?")]}
    
    # Track which tools were called
    tool_calls = []
    for chunk in agent.stream(inputs):
        if "agent" in chunk:
            for msg in chunk["agent"]["messages"]:
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        tool_calls.append(tc["name"])
                elif hasattr(msg, "name") and msg.name:
                    tool_calls.append(msg.name)
                
    # Assert the agent decided to use our SQL querying tool
    # (Note: Could also be SQLDatabaseToolkit's specific tool name, but we look for routing intent)
    assert any("sql" in tool.lower() for tool in tool_calls)


@pytest.mark.integration
def test_agent_hybrid_search():
    """Test Scenario 3: Agent uses SQL to find a service, then Vector DB to find its runbook."""
    agent = create_enterprise_copilot()
    
    # This query requires:
    # 1. SQL to find that /api/v1/checkout belongs to checkout-service
    # 2. Vector search to find the 504 mitigation runbook for checkout-service
    content = "The /api/v1/checkout endpoint is failing with a 504. Who owns it and is there a runbook for it?"
    inputs = {"messages": [HumanMessage(content=content)]}
    
    tool_calls = []
    for chunk in agent.stream(inputs):
        if "agent" in chunk:
            for msg in chunk["agent"]["messages"]:
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        tool_calls.append(tc["name"].lower())
    
    # Assert both tools were considered/invoked
    assert any("sql" in tool for tool in tool_calls)
    assert "search_engineering_docs" in tool_calls
    
    # Final answer should mention the owner (Team Alpha) and the runbook (mitigation steps)
    result = agent.invoke(inputs)
    final_answer = result["messages"][-1].content.lower()
    assert "alpha" in final_answer
    assert "mitigation" in final_answer or "runbook" in final_answer
