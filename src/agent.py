import os
from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import Chroma

load_dotenv()

# Paths
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_FILE = os.path.join(ROOT_DIR, "engineering_data.db")
CHROMA_DB_DIR = os.path.join(ROOT_DIR, "chroma_db")

# Global instances (initialize lazily or via a factory pattern for production, but global is fine for this demo)
embeddings = None
vector_store = None
sql_db = None

def get_vector_store():
    global embeddings, vector_store
    if vector_store is None:
        embeddings = OpenAIEmbeddings()
        vector_store = Chroma(
            persist_directory=CHROMA_DB_DIR, 
            embedding_function=embeddings
        )
    return vector_store

def get_sql_db():
    global sql_db
    if sql_db is None:
        # For absolute paths on Windows with SQLAlchemy, it needs 4 slashes: sqlite:////C:/...
        formatted_path = DB_FILE.replace("\\", "/")
        db_uri = f"sqlite:///{formatted_path}"
        sql_db = SQLDatabase.from_uri(db_uri)
    return sql_db

def close_connections():
    """Close SQL and Vector DB connections to release file locks (primarily for Windows/Tests)."""
    global sql_db, vector_store
    
    if sql_db:
        # LangChain SQLDatabase doesn't have a direct close(), but we can reach the engine
        try:
            sql_db._engine.dispose()
        except:
            pass
        sql_db = None
        
    if vector_store:
        # Chroma releases locks when the object is garbage collected, but we can nudge it
        vector_store = None
    
    print("Closed database connections.")

@tool
def search_engineering_docs(query: str) -> str:
    """Use this tool to search through unstructured engineering documentation like Architecture Decision Records (ADRs) and Runbooks. 
    Use this when you need to understand the concept, rationale, or steps behind a system.
    """
    store = get_vector_store()
    # Retrieve top 3 most relevant chunks
    docs = store.similarity_search(query, k=3)
    
    if not docs:
        return "No relevant documentation found."
        
    # Format the results into a string for the LLM
    formatted_results = []
    for i, doc in enumerate(docs):
        doc_type = doc.metadata.get("document_type", "unknown")
        source = doc.metadata.get("source", "unknown")
        formatted_results.append(f"--- Document {i+1} (Type: {doc_type}, Source: {source}) ---\n{doc.page_content}")
        
    return "\n\n".join(formatted_results)

# For SQL, instead of writing a manual tool, the standard pattern in LangChain is to use the SQLDatabaseToolkit 
# which provides tools to list tables, query schemas, and execute queries. We will expose a simplified wrapper 
# for our tests, keeping in mind the agent will use the toolkit natively later.

@tool
def query_sql_database(query: str) -> str:
    """Use this tool to execute a read-only SQL SELECT query against the structured engineering metadata database.
    If you are unsure of the exact service name, use the SQL LIKE operator (e.g., name LIKE '%service%').
    """
    db = get_sql_db()
    try:
        result = db.run(query)
        return result
    except Exception as e:
        return f"Error executing query: {str(e)}"

@tool
def list_all_services(query: str = "") -> str:
    """Returns a list of all service names currently available in the engineering service catalog.
    Use this if a user asks about a service that returns no results in query_sql_database, so you can discover the correct name.
    """
    db = get_sql_db()
    try:
        # We just want a plain list of names
        result = db.run("SELECT name FROM service_catalog")
        return f"Available services: {result}"
    except Exception as e:
        return f"Error listing services: {str(e)}"

from langgraph.graph import StateGraph, START, END
from langchain.agents import create_agent
from langchain_core.messages import SystemMessage, AnyMessage
from typing import TypedDict, Annotated, Sequence
import operator

# Define the State for the Agent Graph
class AgentState(TypedDict):
    messages: Annotated[Sequence[AnyMessage], operator.add]

def create_enterprise_copilot():
    """Builds and returns a compiled StateGraph containing the routing agent."""
    # 1. Initialize the LLM (Requires OPENAI_API_KEY environment variable)
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    
    # 2. Define the tools the agent has access to
    tools = [search_engineering_docs, query_sql_database, list_all_services]
    
    # 3. Define the System Prompt
    system_prompt = SystemMessage(content='''You are an Enterprise Architecture Copilot.
You help engineers find context about systems, runbooks, and architectures.

You have access to three tools:
1. `search_engineering_docs`: Use this for conceptually finding unstructured Markdown text, like Architecture Decision Records (ADRs) or Runbooks.
2. `query_sql_database`: Use this to query a structured SQLite database. 
3. `list_all_services`: Use this to get a full list of valid service names in our catalog.

**Database Schema:**
- `service_catalog` table: `id`, `name` (the service name), `owner_team`, `version`, `oncall_rotation`, `repository_url`.
- `api_endpoints` table: `id`, `path`, `service_id` (FK to service_catalog), `method`, `description`.

**Guidelines:**
- **Robust SQL Queries**: Service names in the database might have suffixes like `-service`. If a user provides a partial name (e.g. "checkout"), always try using `LIKE '%name%'` in your SQL query first to be robust.
- **Service Discovery**: If `query_sql_database` returns no results for a service name the user provided, use `list_all_services` to find the correct name from the catalog. Suggest the closest matches to the user or try your query again with the correct name.
- **Hybrid Search**: If a question requires information from both the catalog and docs (e.g. "Who owns the service and what is its failover runbook?"), use them sequentially.
- Be concise and technical.''')
    
    # 4. Create the LangChain Agent
    routing_agent = create_agent(llm, tools=tools, system_prompt=system_prompt)
    
    # 5. Define the Node Execution Action
    def agent_node(state: AgentState):
        """Invoke the routing agent and append its response to the state messages."""
        response = routing_agent.invoke(state)
        # return the updated state dict containing the new messages
        return response
        
    # 6. Build the StateGraph
    builder = StateGraph(AgentState)
    builder.add_node("agent", agent_node)
    
    # Define edges: START -> agent -> END
    builder.add_edge(START, "agent")
    builder.add_edge("agent", END)
    
    # Compile the graph
    graph = builder.compile()
    
    
    return graph
