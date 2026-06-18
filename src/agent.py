import logging
import operator
import re
import sqlite3
import threading
from typing import Annotated, NotRequired, Sequence, TypedDict

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_chroma import Chroma
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.utilities import SQLDatabase
from langgraph.graph import END, START, StateGraph
from sqlalchemy import create_engine, text as sql_text
from tenacity import retry, retry_if_not_exception_type, stop_after_attempt, wait_exponential

from src import config
from src.incident_workflow import (
    TriageResult,
    extract_final_assistant_text,
    latest_user_text,
    route_target_for_mode,
)

load_dotenv()

logger = logging.getLogger(__name__)

# Lazy singletons for the embedding/vector/SQL clients. A single lock guards
# all three so close_connections() and cache invalidation are safe from any node.
embeddings = None
vector_store = None
sql_db = None
_prompt_injection_pipeline = None
_state_lock = threading.Lock()


def _clear_vector_store_cache() -> None:
    """Drop cached Chroma client so a rebuild on disk can be picked up."""
    global embeddings, vector_store
    with _state_lock:
        embeddings = None
        vector_store = None


def get_vector_store():
    global embeddings, vector_store
    with _state_lock:
        if vector_store is None:
            embeddings = OpenAIEmbeddings()
            vector_store = Chroma(
                persist_directory=config.chroma_dir(),
                embedding_function=embeddings,
            )
        return vector_store


def get_sql_db():
    global sql_db
    with _state_lock:
        if sql_db is None:
            uri = f"file:{config.db_file().replace(chr(92), '/')}?mode=ro"

            def _connect():
                return sqlite3.connect(uri, uri=True, check_same_thread=False)

            engine = create_engine("sqlite://", creator=_connect)
            sql_db = SQLDatabase(engine=engine)
        return sql_db


def close_connections():
    """Close SQL and Vector DB connections to release file locks (Windows/tests)."""
    global sql_db, vector_store, embeddings
    with _state_lock:
        if sql_db is not None:
            try:
                sql_db._engine.dispose()
            except Exception:
                logger.exception("Failed to dispose SQL engine cleanly")
            sql_db = None
        vector_store = None
        embeddings = None
    print("Closed database connections.")


def _get_prompt_injection_detector():
    """Lazy-load the ProtectAI prompt-injection classifier (HF pipeline)."""
    global _prompt_injection_pipeline
    with _state_lock:
        if _prompt_injection_pipeline is None:
            from transformers import pipeline

            _prompt_injection_pipeline = pipeline(
                "text-classification",
                model=config.prompt_injection_model(),
                truncation=True,
                max_length=512,
            )
        return _prompt_injection_pipeline


def detect_prompt_injection(text: str) -> tuple[bool, float]:
    """Return (is_injection, score).

    Fails open on detector errors so a model-load failure doesn't take down the
    whole agent — we log and let the request through.
    """
    if not text.strip():
        return False, 0.0
    try:
        detector = _get_prompt_injection_detector()
        result = detector(text)[0]
        label = str(result.get("label", "")).upper()
        score = float(result.get("score", 0.0))
        threshold = config.prompt_injection_threshold()
        return (label == "INJECTION" and score >= threshold, score)
    except Exception:
        logger.exception("Prompt-injection detector failed; failing open")
        return False, 0.0


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_not_exception_type((KeyboardInterrupt, SystemExit)),
    reraise=True,
)
def _invoke_with_retry(runnable, inputs):
    """Wrap an LLM/runnable invocation with bounded retry for transient errors."""
    return runnable.invoke(inputs)


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
            "Fix: exit this app, delete the chroma_db folder at the project root, "
            "run `make setup` (or `python -m scripts.setup`), and try again."
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


# Strips SQL line comments (-- ...) and block comments (/* ... */) so the
# SELECT/WITH check can't be bypassed with leading comment noise.
_SQL_COMMENT_RE = re.compile(r"--[^\n]*|/\*.*?\*/", re.DOTALL)
_READONLY_SQL_ERROR = "Read-only mode: only SELECT/WITH statements are allowed."


def _is_readonly_sql(query: str) -> bool:
    """True when `query` is a single SELECT/WITH statement with no stacked statements."""
    stripped = _SQL_COMMENT_RE.sub("", query).strip()
    if not stripped:
        return False
    # Reject anything after the first terminating `;` (blocks stacked statements).
    head, sep, tail = stripped.partition(";")
    if sep and tail.strip():
        return False
    return bool(re.match(r"(?is)^\s*(select|with)\b", head))


@tool
def query_sql_database(query: str) -> str:
    """Use this tool to execute a read-only SQL SELECT query against the structured engineering metadata database.
    If you are unsure of the exact service name, use the SQL LIKE operator (e.g., name LIKE '%service%').
    """
    if not _is_readonly_sql(query):
        return _READONLY_SQL_ERROR
    db = get_sql_db()
    try:
        result = db.run(query)
        return result
    except Exception as e:
        return f"Error executing query: {str(e)}"


@tool
def list_all_services() -> str:
    """Returns a list of all service names currently available in the engineering service catalog.
    Use this if a user asks about a service that returns no results in query_sql_database, so you can discover the correct name.
    """
    db = get_sql_db()
    try:
        result = db.run("SELECT name FROM service_catalog")
        return f"Available services: {result}"
    except Exception as e:
        return f"Error listing services: {str(e)}"


def _escape_like(value: str) -> str:
    """Escape LIKE wildcards so a user-supplied name can't widen the match."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@tool
def query_incidents(service_name: str = "", limit: int = 10) -> str:
    """Returns recent incidents from the incident log, optionally filtered by service name.
    Each row includes severity, time window, a one-line summary, and the postmortem ID (if any).
    Use this when the user asks about historical incidents, recent outages, or what's been
    happening on a service. For deeper context, follow up by searching for the postmortem
    document via search_engineering_docs.
    """
    db = get_sql_db()
    safe_limit = max(1, min(int(limit), 100))
    base_sql = (
        "SELECT i.severity, i.started_at, i.ended_at, s.name, i.summary, i.postmortem_id "
        "FROM incidents i JOIN service_catalog s ON i.service_id = s.id"
    )
    try:
        with db._engine.connect() as conn:
            if service_name:
                stmt = sql_text(
                    f"{base_sql} WHERE s.name LIKE :pattern ESCAPE '\\' "
                    f"ORDER BY i.started_at DESC LIMIT :limit"
                )
                params = {"pattern": f"%{_escape_like(service_name)}%", "limit": safe_limit}
            else:
                stmt = sql_text(
                    f"{base_sql} ORDER BY i.started_at DESC LIMIT :limit"
                )
                params = {"limit": safe_limit}
            rows = conn.execute(stmt, params).fetchall()
            result = [tuple(r) for r in rows]
        return f"Incidents (severity, started_at, ended_at, service, summary, postmortem_id): {result}"
    except Exception as e:
        return f"Error querying incidents: {str(e)}"


def _build_incident_prompt(
    header: str,
    user_text: str,
    triage: dict,
    *,
    sections: dict[str, str] | None = None,
    tail: str = "",
) -> str:
    """Compose the human-message prompt sent to an incident sub-agent."""
    parts = [header, f"User report:\n{user_text}", f"Triage JSON:\n{triage}"]
    for label, value in (sections or {}).items():
        if value:
            parts.append(f"{label}:\n{value}")
    if tail:
        parts.append(tail)
    return "\n\n".join(parts)


# --- Prompts shared by general and subgraph agents ---

_DB_SCHEMA = """**Database Schema:**
- `service_catalog` table: `id`, `name`, `owner_team`, `version`, `oncall_rotation`, `repository_url`,
  `criticality_tier` (`tier-0`/`tier-1`/`tier-2`), `deprecated` (0 or 1), `language`.
- `api_endpoints` table: `id`, `path`, `service_id` (FK to service_catalog), `method`, `description`.
- `incidents` table: `id`, `service_id` (FK), `started_at` (ISO timestamp), `ended_at`, `severity`
  (`SEV-1`/`SEV-2`/`SEV-3`), `summary`, `postmortem_id` (e.g. `PM-2024-001`, may be NULL)."""

_GROUNDING = """**Guidelines:**
- **Ground your answers**: Answer only using information returned by the tools. Do not use general knowledge to fill gaps.
- **Decline out-of-scope questions**: If the user asks about something unrelated to PayLane's services, infrastructure, ADRs, runbooks, postmortems, or incidents (e.g. weather, jokes, general programming help), politely decline and remind them what you can help with.
- **When no docs are found**: Say clearly that no relevant document was found. Do not invent an answer.
- **When SQL has no rows**: Say so; do not make up service or endpoint data.
- **Supersession awareness**: ADRs include `supersedes` / `superseded_by` frontmatter. When asked about a current decision, prefer the latest non-superseded ADR.
- **Robust SQL**: If a user provides a partial service name, use `LIKE '%name%'` when needed.
- **Service discovery**: If SQL returns no rows, use `list_all_services` to find the correct name.
- Be concise and technical."""

GENERAL_SYSTEM_PROMPT = SystemMessage(
    content=f"""You are an Enterprise Architecture Copilot for PayLane (a payment-processing SaaS).
You help engineers find context about systems, runbooks, ADRs, postmortems, design docs, and historical incidents.

You have access to four tools:
1. `search_engineering_docs`: ADRs, runbooks, postmortems, design docs (unstructured markdown).
2. `query_sql_database`: Structured SQLite metadata (services, endpoints, incidents).
3. `list_all_services`: Full list of service names.
4. `query_incidents`: Historical incidents, optionally filtered by service name.

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
- mode=out_of_scope: anything unrelated to PayLane's services, infrastructure, ADRs, runbooks, postmortems, or incidents — e.g. weather, jokes, recipes, world knowledge, generic programming help, personal advice.

When uncertain between incident and general, prefer general for purely conceptual questions and incident when symptoms or error codes are present. Only use out_of_scope when the question clearly has no PayLane engineering angle."""
)

DECLINE_MESSAGE = (
    "I can only help with PayLane's services, runbooks, ADRs, postmortems, and incidents. "
    "Try asking about a service owner, an incident, a design decision, or a runbook."
)


class AgentState(TypedDict):
    messages: Annotated[Sequence[AnyMessage], operator.add]
    mode: NotRequired[str]
    triage: NotRequired[dict]
    structured_findings: NotRequired[str]
    runbook_findings: NotRequired[str]


def _route_after_triage(state: AgentState) -> str:
    return route_target_for_mode(state.get("mode"))


def _route_after_validate(state: AgentState) -> str:
    return "decline_node" if state.get("mode") == "rejected" else "prompt_injection_check"


def _route_after_injection_check(state: AgentState) -> str:
    return "decline_node" if state.get("mode") == "rejected" else "triage"


EMPTY_INPUT_MESSAGE = "I didn't catch a question — could you rephrase?"
PROMPT_INJECTION_MESSAGE = (
    "Your message was flagged as a possible prompt-injection attempt and was blocked. "
    "Please rephrase your question in plain language."
)


def create_enterprise_copilot():
    """Supervisor graph: triage -> incident chain (SQL -> docs -> synthesize) or general ReAct agent."""
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    triage_llm = llm.with_structured_output(TriageResult)

    all_tools = [search_engineering_docs, query_sql_database, list_all_services, query_incidents]
    sql_tools = [query_sql_database, list_all_services, query_incidents]
    doc_tools = [search_engineering_docs]

    general_agent = create_agent(llm, tools=all_tools, system_prompt=GENERAL_SYSTEM_PROMPT)
    structured_agent = create_agent(llm, tools=sql_tools, system_prompt=STRUCTURED_SYSTEM_PROMPT)
    runbook_agent = create_agent(llm, tools=doc_tools, system_prompt=RUNBOOK_SYSTEM_PROMPT)

    def validate_input_node(state: AgentState):
        text = latest_user_text(state["messages"])
        stripped = text.strip()
        cap = config.max_input_chars()
        if not stripped:
            return {
                "mode": "rejected",
                "messages": [AIMessage(content=EMPTY_INPUT_MESSAGE)],
            }
        if len(text) > cap:
            return {
                "mode": "rejected",
                "messages": [
                    AIMessage(
                        content=(
                            f"Your message is {len(text)} chars; the limit is {cap}. "
                            "Please shorten it."
                        )
                    )
                ],
            }
        return {}

    def prompt_injection_check_node(state: AgentState):
        text = latest_user_text(state["messages"])
        is_injection, score = detect_prompt_injection(text)
        if is_injection:
            logger.warning("Blocked likely prompt injection (score=%.3f)", score)
            return {
                "mode": "rejected",
                "messages": [AIMessage(content=PROMPT_INJECTION_MESSAGE)],
            }
        return {}

    def decline_node(state: AgentState):
        # No LLM, no tools — deterministic short-circuit for rejected or out-of-scope inputs.
        if state.get("mode") == "rejected":
            return {}
        return {"messages": [AIMessage(content=DECLINE_MESSAGE)]}

    def triage_node(state: AgentState):
        try:
            triage_messages = [TRIAGE_SYSTEM_PROMPT, *state["messages"]]
            res = _invoke_with_retry(triage_llm, triage_messages)
            tr = res if isinstance(res, TriageResult) else TriageResult(mode="general")
        except Exception:
            logger.exception("Triage LLM failed; defaulting to general mode")
            tr = TriageResult(mode="general")
        return {"mode": tr.mode, "triage": tr.model_dump()}

    def structured_agent_node(state: AgentState):
        prompt = _build_incident_prompt(
            "Incident metadata lookup.",
            latest_user_text(state["messages"]),
            state.get("triage") or {},
            tail=(
                "Use SQL tools to resolve services, endpoints, owners, versions, and on-call. "
                "Then summarize facts in plain text."
            ),
        )
        out = structured_agent.invoke({"messages": [HumanMessage(content=prompt)]})
        findings = extract_final_assistant_text(out["messages"]) or "(no structured findings)"
        return {"messages": out["messages"], "structured_findings": findings}

    def runbook_agent_node(state: AgentState):
        prompt = _build_incident_prompt(
            "Runbook and documentation search for this incident.",
            latest_user_text(state["messages"]),
            state.get("triage") or {},
            sections={"Structured catalog findings": state.get("structured_findings") or ""},
            tail="Call search_engineering_docs with queries that include service names and symptom keywords.",
        )
        out = runbook_agent.invoke({"messages": [HumanMessage(content=prompt)]})
        findings = extract_final_assistant_text(out["messages"]) or "(no runbook snippets)"
        return {"messages": out["messages"], "runbook_findings": findings}

    def synthesize_node(state: AgentState):
        human = HumanMessage(
            content=(
                f"User question:\n{latest_user_text(state['messages'])}\n\n"
                f"---\nStructured findings:\n{state.get('structured_findings') or ''}\n\n"
                f"---\nRunbook/documentation findings:\n{state.get('runbook_findings') or ''}"
            )
        )
        resp = _invoke_with_retry(llm, [SYNTHESIZE_SYSTEM_PROMPT, human])
        return {"messages": [resp]}

    def general_agent_node(state: AgentState):
        return general_agent.invoke(state)

    builder = StateGraph(AgentState)
    builder.add_node("validate_input", validate_input_node)
    builder.add_node("prompt_injection_check", prompt_injection_check_node)
    builder.add_node("decline_node", decline_node)
    builder.add_node("triage", triage_node)
    builder.add_node("structured_agent", structured_agent_node)
    builder.add_node("runbook_agent", runbook_agent_node)
    builder.add_node("synthesize", synthesize_node)
    builder.add_node("general_agent", general_agent_node)

    builder.add_edge(START, "validate_input")
    builder.add_conditional_edges(
        "validate_input",
        _route_after_validate,
        {
            "prompt_injection_check": "prompt_injection_check",
            "decline_node": "decline_node",
        },
    )
    builder.add_conditional_edges(
        "prompt_injection_check",
        _route_after_injection_check,
        {
            "triage": "triage",
            "decline_node": "decline_node",
        },
    )
    builder.add_conditional_edges(
        "triage",
        _route_after_triage,
        {
            "structured_agent": "structured_agent",
            "general_agent": "general_agent",
            "decline_node": "decline_node",
        },
    )
    builder.add_edge("decline_node", END)
    builder.add_edge("structured_agent", "runbook_agent")
    builder.add_edge("runbook_agent", "synthesize")
    builder.add_edge("synthesize", END)
    builder.add_edge("general_agent", END)

    return builder.compile()
