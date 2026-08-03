import asyncio
import logging
import re
import sqlite3
import threading
import time
import uuid
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import Annotated, NotRequired, TypedDict

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.agents.middleware import (
    ClearToolUsesEdit,
    ContextEditingMiddleware,
    SummarizationMiddleware,
)
from langchain_chroma import Chroma
from langchain_community.utilities import SQLDatabase
from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from sqlalchemy import create_engine
from sqlalchemy import text as sql_text
from tenacity import retry, retry_if_not_exception_type, stop_after_attempt, wait_exponential

from src import config
from src.citations import (
    SEARCH_DOCS_TOOL_NAME,
    doc_block_source,
    format_doc_result,
    renumber_doc_block,
    split_doc_blocks,
)
from src.incident_workflow import (
    DocQueryPlan,
    TriageResult,
    extract_final_assistant_text,
    latest_user_text,
    route_target_for_mode,
    trim_history,
)

load_dotenv()

logger = logging.getLogger(__name__)

# Lazy singletons for the embedding/vector/SQL clients. A single lock guards
# all three so close_connections() and cache invalidation are safe from any node.
embeddings = None
vector_store = None
sql_db = None
_prompt_injection_pipeline = None
_catalog_snapshot = None
_catalog_snapshot_at = 0.0
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
    global sql_db, vector_store, embeddings, _catalog_snapshot
    with _state_lock:
        if sql_db is not None:
            try:
                sql_db._engine.dispose()
            except Exception:
                logger.exception("Failed to dispose SQL engine cleanly")
            sql_db = None
        vector_store = None
        embeddings = None
        _catalog_snapshot = None
    print("Closed database connections.")


# --- Service catalog snapshot ------------------------------------------------
#
# The incident path spends most of its wall clock on sequential LLM round trips,
# not on I/O: a SQLite query here costs ~0.1ms, while each round trip costs
# seconds. `structured_agent` was burning three tool calls just to *discover*
# facts (resolve endpoint -> service, then read that service's row) that fit in
# ~800 tokens. Handing it the whole catalog up front turns discovery into a
# lookup the model can do in one pass.
#
# Recent incidents are preloaded too. Once the catalog removed the need for tool
# calls, the model stopped calling `query_incidents` as well, and briefs quietly
# lost their "has this broken before?" section: the eval showed factuality on
# multi-hop-incident dropping 0.87 -> 0.78 while every other category held. They
# are capped by row count as well as by the char budget, because incidents grow
# without bound while a service catalog does not.
#
# This is only sound because the catalog is small (10 services, 24 endpoints) and
# read-only, rebuilt out-of-band by `make setup`. A catalog that did not fit in a
# prompt would have to go back to the SQL tools, which is why those tools stay.


def _format_catalog_snapshot(services, endpoints, incidents=()) -> str:
    """Render catalog rows as compact text for a prompt. Pure: rows in, text out.

    Pipe-delimited rather than JSON to keep the token count down; the header line
    names the columns so the model does not have to infer them positionally.
    """
    if not services and not endpoints and not incidents:
        return ""
    lines: list[str] = []
    if services:
        lines.append(f"Services ({len(services)}):")
        lines.append("name | owner_team | version | oncall | tier | deprecated | language")
        lines += [" | ".join(str(field) for field in row) for row in services]
    if endpoints:
        if lines:
            lines.append("")
        lines.append(f"API endpoints ({len(endpoints)}):")
        lines += [f"{method} {path} -> {service}" for method, path, service in endpoints]
    if incidents:
        if lines:
            lines.append("")
        lines.append(f"Recent incidents ({len(incidents)}), newest first:")
        lines.append("severity | started_at | service | summary | postmortem_id")
        lines += [" | ".join(str(field) for field in row) for row in incidents]
    return "\n".join(lines)


def _build_catalog_snapshot() -> str:
    """Query the catalog and endpoint tables and format them. Empty string on error."""
    db = get_sql_db()
    try:
        with db._engine.connect() as conn:
            services = conn.execute(
                sql_text(
                    "SELECT name, owner_team, version, oncall_rotation, criticality_tier, "
                    "deprecated, language FROM service_catalog ORDER BY name"
                )
            ).fetchall()
            endpoints = conn.execute(
                sql_text(
                    "SELECT e.method, e.path, s.name FROM api_endpoints e "
                    "JOIN service_catalog s ON e.service_id = s.id ORDER BY e.path"
                )
            ).fetchall()
            incidents = conn.execute(
                sql_text(
                    "SELECT i.severity, i.started_at, s.name, i.summary, i.postmortem_id "
                    "FROM incidents i JOIN service_catalog s ON i.service_id = s.id "
                    "ORDER BY i.started_at DESC LIMIT :limit"
                ),
                {"limit": max(0, config.incidents_snapshot_limit())},
            ).fetchall()
    except Exception:
        # Degrade to the SQL tools rather than failing the turn.
        logger.exception("Catalog snapshot build failed; incident path will use SQL tools")
        return ""

    snapshot = _format_catalog_snapshot(
        [tuple(r) for r in services],
        [tuple(r) for r in endpoints],
        [tuple(r) for r in incidents],
    )
    budget = config.catalog_max_chars()
    if budget > 0 and len(snapshot) > budget:
        # Too big to ride in every prompt: fall back to the SQL tools, which is
        # what the structured agent's system prompt tells it to do without a
        # catalog section. This is the knob that keeps the optimization honest
        # on a deployment with thousands of services.
        logger.warning(
            "Catalog snapshot is %d chars (budget %d); falling back to SQL tools",
            len(snapshot),
            budget,
        )
        return ""
    return snapshot


def get_catalog_snapshot() -> str:
    """Cached catalog text for the incident prompts, refreshed on a TTL.

    Cleared eagerly by close_connections(); otherwise re-read every
    config.catalog_ttl_seconds() so a rebuilt DB is picked up without a restart.
    """
    global _catalog_snapshot, _catalog_snapshot_at
    ttl = config.catalog_ttl_seconds()
    now = time.monotonic()
    with _state_lock:
        fresh = ttl <= 0 or (now - _catalog_snapshot_at) < ttl
        if _catalog_snapshot is not None and fresh:
            return _catalog_snapshot
    # Build outside the lock: _build_catalog_snapshot() calls get_sql_db(), which
    # takes this same non-reentrant lock. Two threads racing here both build, which
    # is harmless (a read-only query) and cheaper than making the lock reentrant.
    snapshot = _build_catalog_snapshot()
    with _state_lock:
        _catalog_snapshot = snapshot
        _catalog_snapshot_at = now
        return _catalog_snapshot


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


_RETRY_POLICY = {
    "stop": stop_after_attempt(3),
    "wait": wait_exponential(multiplier=1, min=1, max=8),
    "retry": retry_if_not_exception_type((KeyboardInterrupt, SystemExit)),
    "reraise": True,
}


@retry(**_RETRY_POLICY)
def _invoke_with_retry(runnable, inputs):
    """Wrap an LLM/runnable invocation with bounded retry for transient errors."""
    return runnable.invoke(inputs)


@retry(**_RETRY_POLICY)
async def _ainvoke_with_retry(runnable, inputs):
    """Async twin of `_invoke_with_retry`; tenacity awaits a coroutine function.

    The graph nodes are async so an LLM round trip, which is where the seconds
    are, yields the event loop instead of holding a worker thread. Both share
    `_RETRY_POLICY` so the sync and async paths cannot drift apart.
    """
    return await runnable.ainvoke(inputs)


# Bounds the extra vector-store calls one docs search can trigger, and how far a
# supersession chain is followed before we stop looking for the current ADR.
_MAX_SUPERSESSION_LOOKUPS = 2
_MAX_SUPERSESSION_HOPS = 3
_MAX_ADR_PIN_LOOKUPS = 2


def _first_adr_id(value) -> str:
    """First id from a metadata field like `ADR-002` or `ADR-002,ADR-005`."""
    head = str(value or "").split(",")[0].strip().upper()
    return head


def _doc_key(doc) -> tuple:
    """Identity for de-duplication: same source and same chunk text."""
    return (doc.metadata.get("source", ""), doc.page_content)


def _current_adr(doc, fetch_adr, seen_ids: set[str]):
    """Walk `superseded_by` from `doc` and return the ADR that is current, or None.

    Follows a chain (A superseded by B superseded by C) up to
    _MAX_SUPERSESSION_HOPS, guarding against cycles with `seen_ids`. Lookup
    failures are logged and treated as "no newer ADR", since a degraded search
    still beats a failed one.
    """
    current = None
    next_id = _first_adr_id(doc.metadata.get("superseded_by"))
    seen_ids.add(_first_adr_id(doc.metadata.get("adr_id")))
    for _ in range(_MAX_SUPERSESSION_HOPS):
        if not next_id or next_id in seen_ids:
            break
        seen_ids.add(next_id)
        try:
            fetched = fetch_adr(next_id)
        except Exception:
            logger.exception("Supersession lookup failed for %s", next_id)
            break
        if fetched is None:
            break
        current = fetched
        next_id = _first_adr_id(fetched.metadata.get("superseded_by"))
    return current


def _prefer_current_adrs(docs, fetch_adr, max_lookups: int = _MAX_SUPERSESSION_LOOKUPS):
    """Re-rank retrieval results so a superseded ADR is preceded by the one replacing it.

    Plain top-k cosine search answers "are we still using RabbitMQ?" with the
    superseded ADR, because that is the document the question looks like. For each
    result carrying `superseded_by`, this pulls in the ADR that replaced it and
    ranks it first. The superseded ADR is kept, not dropped: questions about
    history ("what did we use before Kafka?") still need it.

    `fetch_adr(adr_id) -> Document | None` is injected so this stays pure and
    unit-testable; production passes a metadata-filtered vector-store lookup.
    """
    by_adr_id = {
        _first_adr_id(d.metadata.get("adr_id")): d for d in docs if d.metadata.get("adr_id")
    }
    lookups = 0

    def _resolve(adr_id: str):
        """Prefer an already-retrieved chunk over a fresh (billed) store lookup."""
        nonlocal lookups
        if adr_id in by_adr_id:
            return by_adr_id[adr_id]
        if lookups >= max_lookups:
            return None
        lookups += 1
        return fetch_adr(adr_id)

    ordered: list = []
    placed: set[tuple] = set()
    for doc in docs:
        if _doc_key(doc) in placed:
            continue
        if doc.metadata.get("superseded_by"):
            current = _current_adr(doc, _resolve, seen_ids=set())
            if current is not None and _doc_key(current) not in placed:
                ordered.append(current)
                placed.add(_doc_key(current))
        ordered.append(doc)
        placed.add(_doc_key(doc))
    return ordered


# An ADR referenced by id in a question: "ADR-001", "adr 2", "adr_014".
_ADR_QUERY_RE = re.compile(r"\badr[-_\s]?(\d{1,4})\b", re.IGNORECASE)


def _adr_ids_in_query(query: str) -> list[str]:
    """ADR ids a question names explicitly, normalized (`adr 2` -> `ADR-002`).

    De-duplicated, in order of first appearance. Other document families
    (`RB-004`, `PM-2024-001`) are not ADRs and are ignored.
    """
    ids: list[str] = []
    for number in _ADR_QUERY_RE.findall(query or ""):
        adr_id = f"ADR-{int(number):03d}"
        if adr_id not in ids:
            ids.append(adr_id)
    return ids


def _pin_referenced_adrs(docs, query: str, fetch_adr, max_lookups: int = _MAX_ADR_PIN_LOOKUPS):
    """Put ADRs the question names by id at the front of the results.

    Cosine similarity is weak on bare identifiers: "Is ADR-001 still in effect?"
    embeds like every other governance sentence in the corpus and retrieves
    unrelated documents. The `adr_id` metadata index answers it exactly, so an
    ADR the question names is fetched directly and ranked first (the supersession
    pass then pulls in whatever replaced it).
    """
    present = {_first_adr_id(d.metadata.get("adr_id")) for d in docs if d.metadata.get("adr_id")}
    pinned = []
    for adr_id in _adr_ids_in_query(query)[:max_lookups]:
        if adr_id in present:
            continue
        try:
            fetched = fetch_adr(adr_id)
        except Exception:
            logger.exception("ADR lookup failed for %s", adr_id)
            continue
        if fetched is not None:
            pinned.append(fetched)
            present.add(adr_id)
    return pinned + list(docs)


def _supersession_note(metadata: dict) -> str | None:
    """One-line status for an ADR result, so the model can see it is (not) current."""
    if superseded_by := metadata.get("superseded_by"):
        return f"Status: superseded by {superseded_by}"
    if supersedes := metadata.get("supersedes"):
        return f"Status: current; supersedes {supersedes}"
    return None


@tool
def search_engineering_docs(query: str) -> str:
    """Use this tool to search through unstructured engineering documentation like Architecture Decision Records (ADRs) and Runbooks.
    Use this when you need to understand the concept, rationale, or steps behind a system.
    Pass the user's full question as the query, adding service names or error codes you already know.
    Two-word keyword queries retrieve worse than a sentence, and an ADR referenced by id (e.g. "ADR-002") is looked up exactly.
    """
    try:
        store = get_vector_store()
        docs = store.similarity_search(query, k=3)

        def fetch_adr(adr_id: str):
            """Most query-relevant chunk of one ADR, by its indexed adr_id."""
            hits = store.similarity_search(query, k=1, filter={"adr_id": adr_id})
            return hits[0] if hits else None

        docs = _pin_referenced_adrs(docs, query, fetch_adr)
        docs = _prefer_current_adrs(docs, fetch_adr)
    except Exception as e:
        _clear_vector_store_cache()
        err = str(e)
        hint = (
            "Fix: exit this app, delete the chroma_db folder at the project root, "
            "run `make setup` (or `python -m scripts.setup`), and try again."
        )
        if "tenant" in err.lower() or "default_tenant" in err:
            hint = (
                "This usually means chroma_db is missing, incomplete, or from another ChromaDB version. "
                + hint
            )
        return f"Vector database error ({err}). {hint}"

    if not docs:
        return "No relevant documentation found."

    formatted_results = []
    for i, doc in enumerate(docs):
        doc_type = doc.metadata.get("document_type", "unknown")
        source = doc.metadata.get("source", "unknown")
        formatted_results.append(
            format_doc_result(
                i + 1,
                doc_type,
                source,
                doc.page_content,
                note=_supersession_note(doc.metadata),
            )
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
                stmt = sql_text(f"{base_sql} ORDER BY i.started_at DESC LIMIT :limit")
                params = {"limit": safe_limit}
            rows = conn.execute(stmt, params).fetchall()
            result = [tuple(r) for r in rows]
        return (
            f"Incidents (severity, started_at, ended_at, service, summary, postmortem_id): {result}"
        )
    except Exception as e:
        return f"Error querying incidents: {str(e)}"


# --- Runbook document search (planner + parallel search, no ReAct loop) ------
#
# The runbook step used to be a ReAct sub-agent, which always spends a second LLM
# call turning the retrieved chunks into prose. `synthesize` then summarized that
# prose again, so the documents were compressed twice and the second pass cost
# ~2.3s. Here the model is asked once for its search queries, the searches run in
# parallel, and the retrieved text goes to `synthesize` intact, with its
# `Cite as: [doc-id]` lines still attached.
#
# The searches are still recorded as real AIMessage(tool_calls) + ToolMessage
# pairs. That is not cosmetic: `extract_retrieved_sources` reads ToolMessages, so
# retrieval_precision, retrieval_recall and citation_validity all go blind without
# them, and the UI renders its tool chips from the same messages.


def _search_docs_parallel(queries: Sequence[str], search=None) -> list[str]:
    """Run doc searches concurrently, returning results in `queries` order.

    `search` is injected for tests; production passes the real tool. One failing
    search degrades to an error string rather than failing the whole step, which
    matches how `search_engineering_docs` already handles vector-store errors.
    """
    if not queries:
        return []
    run = search or (lambda q: search_engineering_docs.invoke({"query": q}))

    def _one(query: str) -> str:
        try:
            return run(query)
        except Exception as exc:
            logger.exception("Doc search failed for %r", query)
            return f"Search failed for this query ({exc})."

    with ThreadPoolExecutor(max_workers=len(queries)) as pool:
        return list(pool.map(_one, queries))


async def _asearch_docs_parallel(queries: Sequence[str], search=None) -> list[str]:
    """Async twin of `_search_docs_parallel`, for the async graph nodes.

    Chroma has no native async client: `asimilarity_search` is a thread shim in
    langchain-core's base class. Awaiting it is still the right call, because the
    shim yields the event loop while the worker thread runs, where a direct sync
    call from an async node would block every other in-flight request.
    """
    if not queries:
        return []
    run = search or (lambda q: search_engineering_docs.ainvoke({"query": q}))

    async def _one(query: str) -> str:
        try:
            return await run(query)
        except Exception as exc:
            logger.exception("Doc search failed for %r", query)
            return f"Search failed for this query ({exc})."

    return list(await asyncio.gather(*(_one(q) for q in queries)))


def _doc_tool_messages(queries: Sequence[str], results: Sequence[str]) -> list:
    """One AIMessage announcing the searches, plus a ToolMessage per result.

    Mirrors what a ReAct step would have written into state, so the retrieval
    evaluators and the UI keep seeing the searches after the loop is gone.
    """
    if not queries:
        return []
    calls = [
        {"name": SEARCH_DOCS_TOOL_NAME, "args": {"query": q}, "id": str(uuid.uuid4())}
        for q in queries
    ]
    messages: list = [AIMessage(content="", tool_calls=calls)]
    messages += [
        ToolMessage(content=result, name=SEARCH_DOCS_TOOL_NAME, tool_call_id=call["id"])
        for call, result in zip(calls, results, strict=False)
    ]
    return messages


def _merge_doc_results(results: Sequence[str], max_blocks: int = 0, max_chars: int = 0) -> str:
    """Merge search results into the bounded document set `synthesize` reads.

    Near-identical queries return overlapping documents, and a plain concatenation
    hands `synthesize` thousands of tokens of partly-irrelevant context. De-dupes
    identical blocks, renumbers, and caps both block count and total size.

    Blocks are interleaved by rank (every query's best hit, then every query's
    second, ...) rather than taken query by query. The planner is asked for
    complementary queries, so a query-major order meant the cap could drop a whole
    query's results instead of trimming each query's tail: with 3 queries of 3 hits
    and a cap of 6, the third query contributed nothing. Briefs then answered
    correctly from the wrong half of the corpus, scoring 1.0 on groundedness while
    losing factuality for never citing the runbook the question was about.
    """
    max_blocks = max_blocks or config.runbook_max_blocks()
    max_chars = max_chars or config.runbook_max_chars()

    per_query = [split_doc_blocks(result) for result in results]
    kept: list[str] = []
    seen: set[str] = set()
    sources: set[str] = set()
    total = 0

    def _take(block: str) -> None:
        nonlocal total
        if block in seen or len(kept) >= max_blocks:
            return
        addition = len(block) + 2
        if kept and total + addition > max_chars:
            return
        seen.add(block)
        sources.add(doc_block_source(block))
        kept.append(renumber_doc_block(block, len(kept) + 1))
        total += addition

    ranked = [
        blocks[rank]
        for rank in range(max((len(b) for b in per_query), default=0))
        for blocks in per_query
        if rank < len(blocks)
    ]
    # Breadth before depth: one block per source document first, then spend any
    # leftover budget on further chunks. One document often supplies several
    # chunks, and filling the budget with them buries a document the question
    # needed (the brief that "lacks specific reference to RB-015" had RB-015
    # retrieved, just cut).
    for block in ranked:
        if doc_block_source(block) not in sources:
            _take(block)
    for block in ranked:
        _take(block)
    return "\n\n".join(kept)


def _fallback_doc_queries(triage: dict, user_text: str) -> list[str]:
    """Search queries built from triage hints, for when the planner LLM fails.

    Triage already extracts the service, endpoint and symptoms, which is most of
    what the planner would have written. Full sentences, not bare keywords: the
    tool's own docstring notes two-word queries retrieve worse.
    """
    subject = (triage or {}).get("service_hint") or (triage or {}).get("endpoint_hint") or ""
    symptoms = (triage or {}).get("symptoms_summary") or ""
    stem = (
        " ".join(part for part in (subject, symptoms) if part).strip() or (user_text or "").strip()
    )
    if not stem:
        return []
    return [f"{stem} runbook mitigation steps", f"{stem} postmortem incident history"]


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
- **An empty SQL result is not proof something never happened.** The tables hold services, endpoints, and recent incidents; they do NOT hold postmortems, ADRs, runbooks, or older incident history. Before concluding that an incident, outage, or decision does not exist, search the documentation with `search_engineering_docs` using the words the user used. Say "I found no record" only after both a catalog lookup and a document search came back empty. Denying a real incident is worse than saying you are unsure.
- **Supersession awareness**: Technology choices live in ADRs, not in the service catalog, so answer "are we still using X?" or "what is our current Y?" with `search_engineering_docs`, never from SQL alone. Each ADR result carries a `Status:` line (`superseded by ADR-NNN`, or `current; supersedes ADR-NNN`). Answer from the current ADR and name the superseded one only as history.
- **Robust SQL**: If a user provides a partial service name, use `LIKE '%name%'` when needed.
- **Service discovery**: If SQL returns no rows, use `list_all_services` to find the correct name.
- **Cite your sources**: Each `search_engineering_docs` result includes a `Cite as: [doc-id]` line. When you state a fact from a document, cite it inline with that exact tag, e.g. `[001-checkout-504-mitigation]`. Only cite doc-ids that appeared in a tool result; never invent one. End a document-grounded answer with a `**Sources:**` line listing the doc-ids you cited.
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
    content=f"""You are a metadata specialist for an active incident. Use ONLY `query_sql_database`, `list_all_services`, and `query_incidents`.
Resolve API paths to services, then return owner team, version, on-call rotation, and repository URL when available.

**A `Service catalog` section is usually provided in the user message. Treat it as already-run
SQL.** Its `Services` and `API endpoints` lists are complete. Answer ownership, version,
on-call, tier, and endpoint-to-service questions directly from them and do NOT call a tool to
re-fetch what they already show. Fall back to the SQL tools if the section is missing or lacks
the row you need.

**The `Recent incidents` rows are only the newest few, NOT the full incident history.** Two
rules follow:

- *Never conclude an incident did not happen because it is absent here.* The corpus also holds
  postmortems for older incidents. If the user names an incident you cannot see, say it is
  outside the recent window and let the documentation search find its postmortem. Denying a
  real incident is the worst error you can make.
- *Only quote a date, severity, or postmortem id from a row you have positively matched* to the
  service AND the symptom in the question. These rows list many unrelated incidents, and
  copying the date from the wrong one is a factual error. If no row matches, give no date
  rather than the nearest-looking one.

Report prior incidents for the affected service when a row genuinely matches it. If none does,
say "no incidents in the recent window" and note that older ones may exist.

{_DB_SCHEMA}

{_GROUNDING}
Output a compact factual summary for the runbook step; do not write a customer-facing incident brief yet."""
)

RUNBOOK_PLANNER_PROMPT = SystemMessage(
    content="""You plan the documentation searches for an active incident. You do not answer the question.

Return 1-3 search queries against a corpus of runbooks, ADRs, postmortems, and design docs.
Each query must be a short sentence that names the service (or the endpoint path when the
service is unknown), the symptom or error code, and what is wanted: "runbook", "mitigation
steps", or "postmortem". Bare two-word keyword queries retrieve poorly.

Make the queries complement each other rather than restate one another: for example one for
mitigation steps, one for prior incidents. Return only the queries."""
)

SYNTHESIZE_SYSTEM_PROMPT = SystemMessage(
    content="""You synthesize the final **incident brief** for the engineer on call. Use ONLY the structured findings, the retrieved documents below, and the user question. If something is missing, state the gap explicitly.

Use this structure:

## Summary
## Ownership / paging
## Runbook / mitigation steps
## Evidence (what the tools returned)
## Gaps
## Sources

Do not invent service names, teams, or runbook steps not supported by the findings.

The retrieved documents are raw search results, so some will be irrelevant to this incident:
judge each one on whether it actually matches the service and symptom, and ignore the rest
rather than working them into the brief. Retrieval is not endorsement.

**Answer the question that was asked, and stop.** Include a fact only if it bears on this
incident: who owns the failing thing, what is wrong, how to mitigate it. Leave out background,
unrelated history, adjacent services, and detail from a document that merely matched the
search. A short brief that answers the question is better than a long one that surveys the
corpus, and every extra claim is another chance to be wrong. Prefer no date to a date you are
not certain applies to *this* incident.

Each retrieved document carries a `Cite as: [doc-id]` line (e.g. `[001-checkout-504-mitigation]`).
Cite that exact tag inline where you use a fact from it, and list the tags you used under
`## Sources`. Only cite doc-ids that appear in the documents below; never invent one.

The structured findings (service ownership, versions, on-call, incident history) come from the
service catalog, not from a document. They are **not citable**: state them plainly with no tag,
and never attach a doc-id to them. If a fact has no `Cite as:` line behind it, it gets no
citation. Leaving a true statement uncited is correct; attaching the wrong doc-id is not."""
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


_sync_bridge = threading.local()


def _bridge_event_loop() -> asyncio.AbstractEventLoop:
    """Return this thread's dedicated event loop, creating it on first use.

    The loop is deliberately kept open for the life of the thread. `asyncio.run`
    closes the loop it creates, and on Windows that runs `IocpProactor.close()`,
    which polls until every outstanding overlapped read completes. The pooled
    HTTP sockets inside `ChatOpenAI` are never explicitly closed, so their reads
    stay outstanding after the peer hangs up and that poll blocks forever. One
    reused loop skips the teardown path entirely, and stops rebuilding a loop and
    its client connections once per call.
    """
    loop = getattr(_sync_bridge, "loop", None)
    if loop is None or loop.is_closed():
        loop = asyncio.new_event_loop()
        # Libraries that call bare `get_event_loop()` must find this same loop.
        asyncio.set_event_loop(loop)
        _sync_bridge.loop = loop
    return loop


def invoke_sync(graph, inputs, config=None):
    """Run the graph to completion from synchronous code.

    The graph's nodes are `async def`, so LangGraph refuses a plain `.invoke()`
    ("No synchronous function provided"). Synchronous callers that cannot be made
    async, notably `langsmith.evaluate()`'s target and one-shot scripts, go
    through here. Anything already inside an event loop (the FastAPI app, the CLI)
    must await `ainvoke`/`astream` directly.

    Safe to call from several threads at once, as `langsmith.evaluate()` does:
    each thread drives its own loop.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass  # No loop on this thread, which is the case this bridge is for.
    else:
        raise RuntimeError(
            "invoke_sync() cannot be called from a thread with a running event loop. "
            "Await graph.ainvoke(...) or graph.astream(...) directly instead."
        )
    return _bridge_event_loop().run_until_complete(graph.ainvoke(inputs, config))


class AgentState(TypedDict):
    # add_messages (not operator.add) dedupes by message id, so a subgraph that
    # echoes prior messages doesn't duplicate them, and a checkpointer can persist
    # a clean conversation across turns.
    messages: Annotated[Sequence[AnyMessage], add_messages]
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


def create_enterprise_copilot(checkpointer=None):
    """Supervisor graph: triage -> incident chain (SQL -> docs -> synthesize) or general ReAct agent.

    Pass a checkpointer (e.g. MemorySaver) to persist per-thread conversation state
    for multi-turn use; default None compiles a stateless graph (evals, LangGraph
    Platform, which injects its own persistence).

    Context growth in the ReAct agents is managed with LangChain middleware: the
    general agent uses SummarizationMiddleware (summarize older turns, keep recent),
    and the incident sub-agents use ContextEditingMiddleware (clear stale tool
    results). Thresholds are env-configurable via config.summarization_* and
    config.context_edit_*. The hand-written triage/synthesize nodes are plain LLM
    calls and continue to bound history with trim_history.
    """
    # timeout is not optional: without a deadline a dead socket produces an await
    # that never resolves, which no retry policy can rescue because no exception is
    # ever raised. With one, `_ainvoke_with_retry` gets an error it can retry.
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        timeout=config.llm_timeout_seconds(),
    )
    triage_llm = llm.with_structured_output(TriageResult)

    all_tools = [search_engineering_docs, query_sql_database, list_all_services, query_incidents]
    sql_tools = [query_sql_database, list_all_services, query_incidents]

    # The conversational general agent summarizes older turns (multi-turn history
    # matters); the single-shot incident sub-agents clear stale tool results, which
    # are the bulk of their in-loop token growth. See create_enterprise_copilot docstring.
    summarization_mw = SummarizationMiddleware(
        model=llm,
        trigger=("tokens", config.summarization_trigger_tokens()),
        keep=("messages", config.summarization_keep_messages()),
    )
    context_editing_mw = ContextEditingMiddleware(
        edits=[
            ClearToolUsesEdit(
                trigger=config.context_edit_trigger_tokens(),
                keep=config.context_edit_keep_tool_results(),
            )
        ]
    )

    general_agent = create_agent(
        llm, tools=all_tools, system_prompt=GENERAL_SYSTEM_PROMPT, middleware=[summarization_mw]
    )
    structured_agent = create_agent(
        llm,
        tools=sql_tools,
        system_prompt=STRUCTURED_SYSTEM_PROMPT,
        middleware=[context_editing_mw],
    )
    # No ReAct agent for the runbook step: it plans its searches in one structured
    # call, runs them in parallel, and hands the retrieved text to `synthesize`.
    runbook_planner_llm = llm.with_structured_output(DocQueryPlan)

    async def validate_input_node(state: AgentState):
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
        # Reset per-turn scratch on success. With a checkpointer these persist across
        # turns, so a thread whose previous turn was "rejected" would otherwise route
        # straight back to decline_node forever.
        return {
            "mode": "",
            "triage": {},
            "structured_findings": "",
            "runbook_findings": "",
        }

    async def prompt_injection_check_node(state: AgentState):
        text = latest_user_text(state["messages"])
        # DeBERTa inference is CPU-bound (~60ms). Run it in a thread: awaiting it
        # inline would block every other in-flight request for that whole time.
        is_injection, score = await asyncio.to_thread(detect_prompt_injection, text)
        if is_injection:
            logger.warning("Blocked likely prompt injection (score=%.3f)", score)
            return {
                "mode": "rejected",
                "messages": [AIMessage(content=PROMPT_INJECTION_MESSAGE)],
            }
        return {}

    async def decline_node(state: AgentState):
        # No LLM, no tools — deterministic short-circuit for rejected or out-of-scope inputs.
        if state.get("mode") == "rejected":
            return {}
        return {"messages": [AIMessage(content=DECLINE_MESSAGE)]}

    async def triage_node(state: AgentState):
        try:
            history = trim_history(state["messages"], config.history_max_messages())
            triage_messages = [TRIAGE_SYSTEM_PROMPT, *history]
            res = await _ainvoke_with_retry(triage_llm, triage_messages)
            tr = res if isinstance(res, TriageResult) else TriageResult(mode="general")
        except Exception:
            logger.exception("Triage LLM failed; defaulting to general mode")
            tr = TriageResult(mode="general")
        return {"mode": tr.mode, "triage": tr.model_dump()}

    async def structured_agent_node(state: AgentState):
        prompt = _build_incident_prompt(
            "Incident metadata lookup.",
            latest_user_text(state["messages"]),
            state.get("triage") or {},
            sections={"Service catalog": get_catalog_snapshot()},
            tail=(
                "Resolve services, endpoints, owners, versions, on-call, and prior "
                "incidents from the Service catalog above. Call a SQL tool only for what "
                "it does not cover. Then summarize facts in plain text, including whether "
                "the affected service has prior incidents."
            ),
        )
        out = await structured_agent.ainvoke({"messages": [HumanMessage(content=prompt)]})
        findings = extract_final_assistant_text(out["messages"]) or "(no structured findings)"
        return {"messages": out["messages"], "structured_findings": findings}

    async def runbook_agent_node(state: AgentState):
        triage = state.get("triage") or {}
        user_text = latest_user_text(state["messages"])
        prompt = _build_incident_prompt(
            "Plan the documentation searches for this incident.",
            user_text,
            triage,
            sections={"Structured catalog findings": state.get("structured_findings") or ""},
            tail="Return the search queries only. Do not answer the question.",
        )
        try:
            plan = await _ainvoke_with_retry(
                runbook_planner_llm, [RUNBOOK_PLANNER_PROMPT, HumanMessage(content=prompt)]
            )
            queries = list(plan.queries) if isinstance(plan, DocQueryPlan) else []
        except Exception:
            logger.exception("Runbook query planning failed; falling back to triage hints")
            queries = []

        # De-dupe and bound before searching: the planner occasionally repeats a
        # query, and each one costs an embedding round trip.
        seen: set[str] = set()
        queries = [
            q.strip()
            for q in queries
            if q and q.strip() and not (q.strip().lower() in seen or seen.add(q.strip().lower()))
        ][: config.runbook_max_queries()]
        if not queries:
            queries = _fallback_doc_queries(triage, user_text)

        results = await _asearch_docs_parallel(queries)
        findings = _merge_doc_results(results) or "(no runbook snippets)"
        return {
            "messages": _doc_tool_messages(queries, results),
            "runbook_findings": findings,
        }

    async def synthesize_node(state: AgentState):
        human = HumanMessage(
            content=(
                f"User question:\n{latest_user_text(state['messages'])}\n\n"
                f"---\nStructured findings:\n{state.get('structured_findings') or ''}\n\n"
                f"---\nRetrieved documents:\n{state.get('runbook_findings') or ''}"
            )
        )
        resp = await _ainvoke_with_retry(llm, [SYNTHESIZE_SYSTEM_PROMPT, human])
        return {"messages": [resp]}

    async def general_agent_node(state: AgentState):
        history = trim_history(state["messages"], config.history_max_messages())
        return await general_agent.ainvoke({**state, "messages": history})

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

    return builder.compile(checkpointer=checkpointer)
