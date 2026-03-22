import operator
import os
from typing import Annotated, NotRequired, Sequence, TypedDict

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_community.vectorstores import Chroma
from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.utilities import SQLDatabase
from langgraph.graph import END, START, StateGraph

from src.incident_workflow import (
    TriageResult,
    extract_final_assistant_text,
    latest_user_text,
    route_target_for_mode,
)

load_dotenv()

# Paths
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_FILE = os.path.join(ROOT_DIR, "engineering_data.db")
CHROMA_DB_DIR = os.path.join(ROOT_DIR, "chroma_db")

# Global instances (initialize lazily or via a factory pattern for production, but global is fine for this demo)
embeddings = None
vector_store = None
sql_db = None


def _clear_vector_store_cache() -> None:
    """Drop cached Chroma client so a rebuild on disk can be picked up."""
    global embeddings, vector_store
    embeddings = None
    vector_store = None


def get_vector_store():
    global embeddings, vector_store
    if vector_store is None:
        embeddings = OpenAIEmbeddings()
        vector_store = Chroma(
            persist_directory=CHROMA_DB_DIR,
            embedding_function=embeddings,
        )
    return vector_store


def get_sql_db():
    global sql_db
    if sql_db is None:
        formatted_path = DB_FILE.replace("\\", "/")
        db_uri = f"sqlite:///{formatted_path}"
        sql_db = SQLDatabase.from_uri(db_uri)
    return sql_db


def close_connections():
    """Close SQL and Vector DB connections to release file locks (primarily for Windows/Tests)."""
    global sql_db, vector_store

    if sql_db:
        try:
            sql_db._engine.dispose()
        except Exception:
            pass
        sql_db = None

    if vector_store:
        vector_store = None

    print("Closed database connections.")


@tool
def search_engineering_docs(query: str) -> str:
    """Use this tool to search through unstructured engineering documentation like Architecture Decision Records (ADRs) and Runbooks.
    Use this when you need to understand the concept, rationale, or steps behind a system.
    """
    try:
        store = get_vector_store()
        docs = store.similarity_search(query, k=3)
    except Exception as e:
        _clear_vector_store_cache()
        err = str(e)
        hint = (
            "Fix: exit this app, delete the chroma_db folder at the project root, run "
            "`python src/generate_mock_data.py` then `python src/build_vector_db.py`, and try again."
        )
        if "tenant" in err.lower() or "default_tenant" in err:
            hint = (
                "This usually means chroma_db is missing, incomplete, or from another ChromaDB version. " + hint
            )
        return f"Vector database error ({err}). {hint}"

    if not docs:
        return "No relevant documentation found."

    formatted_results = []
    for i, doc in enumerate(docs):
        doc_type = doc.metadata.get("document_type", "unknown")
        source = doc.metadata.get("source", "unknown")
        formatted_results.append(
            f"--- Document {i+1} (Type: {doc_type}, Source: {source}) ---\n{doc.page_content}"
        )

    return "\n\n".join(formatted_results)


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
        result = db.run("SELECT name FROM service_catalog")
        return f"Available services: {result}"
    except Exception as e:
        return f"Error listing services: {str(e)}"


# --- Prompts shared by general and subgraph agents ---

_DB_SCHEMA = """**Database Schema:**
- `service_catalog` table: `id`, `name` (the service name), `owner_team`, `version`, `oncall_rotation`, `repository_url`.
- `api_endpoints` table: `id`, `path`, `service_id` (FK to service_catalog), `method`, `description`."""

_GROUNDING = """**Guidelines:**
- **Ground your answers**: Answer only using information returned by the tools. Do not use general knowledge to fill gaps.
- **When no docs are found**: Say clearly that no relevant document was found. Do not invent an answer.
- **When SQL has no rows**: Say so; do not make up service or endpoint data.
- **Robust SQL**: If a user provides a partial service name, use `LIKE '%name%'` when needed.
- **Service discovery**: If SQL returns no rows, use `list_all_services` to find the correct name.
- Be concise and technical."""

GENERAL_SYSTEM_PROMPT = SystemMessage(
    content=f"""You are an Enterprise Architecture Copilot.
You help engineers find context about systems, runbooks, and architectures.

You have access to three tools:
1. `search_engineering_docs`: ADRs and runbooks (unstructured).
2. `query_sql_database`: Structured SQLite metadata.
3. `list_all_services`: Full list of service names.

{_DB_SCHEMA}

{_GROUNDING}
- **Hybrid Search**: If a question needs both catalog and docs, use tools sequentially."""
)

STRUCTURED_SYSTEM_PROMPT = SystemMessage(
    content=f"""You are a metadata specialist for an active incident. Use ONLY `query_sql_database` and `list_all_services`.
Resolve API paths to services, then return owner team, version, on-call rotation, and repository URL when available.

{_DB_SCHEMA}

{_GROUNDING}
Output a compact factual summary for the runbook step; do not write a customer-facing incident brief yet."""
)

RUNBOOK_SYSTEM_PROMPT = SystemMessage(
    content=f"""You are a documentation specialist for an active incident. Use ONLY `search_engineering_docs`.
Search for runbooks, mitigations, and operational steps relevant to the service and symptoms described.
Prefer queries that include service name, error type (e.g. 504), and words like "mitigation" or "runbook".

{_GROUNDING}"""
)

SYNTHESIZE_SYSTEM_PROMPT = SystemMessage(
    content="""You synthesize the final **incident brief** for the engineer on call. Use ONLY the structured and runbook sections below plus the user question. If something is missing, state the gap explicitly.

Use this structure:

## Summary
## Ownership / paging
## Runbook / mitigation steps
## Evidence (what the tools returned)
## Gaps

Do not invent service names, teams, or runbook steps not supported by the findings."""
)

TRIAGE_SYSTEM_PROMPT = SystemMessage(
    content="""Classify the user's message.

- mode=incident: production or staging issues, outages, HTTP errors (4xx/5xx), timeouts, latency, "who owns this endpoint", paging/on-call during an active problem, or runbook/mitigation for a failing path.
- mode=general: architecture rationale (ADRs), "why did we choose X", design history, or simple catalog lookups (version, owner) with no incident context.

When uncertain, prefer general for purely conceptual questions and incident when symptoms or error codes are present."""
)


class AgentState(TypedDict):
    messages: Annotated[Sequence[AnyMessage], operator.add]
    mode: NotRequired[str]
    triage: NotRequired[dict]
    structured_findings: NotRequired[str]
    runbook_findings: NotRequired[str]


def _route_after_triage(state: AgentState) -> str:
    return route_target_for_mode(state.get("mode"))


def create_enterprise_copilot():
    """Supervisor graph: triage -> incident chain (SQL -> docs -> synthesize) or general ReAct agent."""
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    triage_llm = llm.with_structured_output(TriageResult)

    all_tools = [search_engineering_docs, query_sql_database, list_all_services]
    sql_tools = [query_sql_database, list_all_services]
    doc_tools = [search_engineering_docs]

    general_agent = create_agent(llm, tools=all_tools, system_prompt=GENERAL_SYSTEM_PROMPT)
    structured_agent = create_agent(llm, tools=sql_tools, system_prompt=STRUCTURED_SYSTEM_PROMPT)
    runbook_agent = create_agent(llm, tools=doc_tools, system_prompt=RUNBOOK_SYSTEM_PROMPT)

    def triage_node(state: AgentState):
        try:
            triage_messages = [TRIAGE_SYSTEM_PROMPT, *state["messages"]]
            res = triage_llm.invoke(triage_messages)
            if isinstance(res, TriageResult):
                tr = res
            else:
                tr = TriageResult(mode="general")
        except Exception:
            tr = TriageResult(mode="general")
        return {"mode": tr.mode, "triage": tr.model_dump()}

    def structured_agent_node(state: AgentState):
        user_text = latest_user_text(state["messages"])
        triage = state.get("triage") or {}
        prompt = (
            "Incident metadata lookup.\n\n"
            f"User report:\n{user_text}\n\n"
            f"Triage JSON:\n{triage}\n\n"
            "Use SQL tools to resolve services, endpoints, owners, versions, and on-call. "
            "Then summarize facts in plain text."
        )
        out = structured_agent.invoke({"messages": [HumanMessage(content=prompt)]})
        findings = extract_final_assistant_text(out["messages"]) or "(no structured findings)"
        return {"messages": out["messages"], "structured_findings": findings}

    def runbook_agent_node(state: AgentState):
        user_text = latest_user_text(state["messages"])
        structured = state.get("structured_findings") or ""
        triage = state.get("triage") or {}
        prompt = (
            "Runbook and documentation search for this incident.\n\n"
            f"User report:\n{user_text}\n\n"
            f"Triage JSON:\n{triage}\n\n"
            f"Structured catalog findings:\n{structured}\n\n"
            "Call search_engineering_docs with queries that include service names and symptom keywords."
        )
        out = runbook_agent.invoke({"messages": [HumanMessage(content=prompt)]})
        findings = extract_final_assistant_text(out["messages"]) or "(no runbook snippets)"
        return {"messages": out["messages"], "runbook_findings": findings}

    def synthesize_node(state: AgentState):
        user_text = latest_user_text(state["messages"])
        structured = state.get("structured_findings") or ""
        runbook = state.get("runbook_findings") or ""
        human = HumanMessage(
            content=(
                f"User question:\n{user_text}\n\n---\nStructured findings:\n{structured}\n\n"
                f"---\nRunbook/documentation findings:\n{runbook}"
            )
        )
        resp = llm.invoke([SYNTHESIZE_SYSTEM_PROMPT, human])
        return {"messages": [resp]}

    def general_agent_node(state: AgentState):
        return general_agent.invoke(state)

    builder = StateGraph(AgentState)
    builder.add_node("triage", triage_node)
    builder.add_node("structured_agent", structured_agent_node)
    builder.add_node("runbook_agent", runbook_agent_node)
    builder.add_node("synthesize", synthesize_node)
    builder.add_node("general_agent", general_agent_node)

    builder.add_edge(START, "triage")
    builder.add_conditional_edges(
        "triage",
        _route_after_triage,
        {
            "structured_agent": "structured_agent",
            "general_agent": "general_agent",
        },
    )
    builder.add_edge("structured_agent", "runbook_agent")
    builder.add_edge("runbook_agent", "synthesize")
    builder.add_edge("synthesize", END)
    builder.add_edge("general_agent", END)

    return builder.compile()
