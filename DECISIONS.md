# Architecture & Technology Decisions Log

This document tracks the rationale behind key technical choices for the Enterprise Architecture Copilot.

## 1. Project Initialization & Dependencies

### Python Virtual Environment (`venv`)
*   **Decision:** Use standard Python `venv` with a `requirements.txt`.
*   **Rationale:** Keeps dependencies isolated and makes the project easily reproducible.

### LangChain Ecosystem (`langchain`, `langgraph`, `langsmith`)
*   **Decision:** Build the agentic routing logic using LangChain v0.3.x and LangGraph.
*   **Rationale:** LangChain provides the standard abstractions for vector stores and LLM interactions. LangGraph is newly preferred (v1.0 best practices) over legacy `AgentExecutor` for building reliable, cyclical agent decision trees (the "Router" aspect of this project).

### Structured Database (`sqlite3` / `SQLAlchemy`)
*   **Decision:** Use SQLite for the structured data store, managed via the standard `sqlite3` library (with `SQLAlchemy` loaded for future ORM needs if complexity grows).
*   **Rationale:** Zero-configuration. Perfect for a local demonstration of structured metadata querying without the overhead of spinning up a Postgres container.

### Unstructured Database (`chromadb`)
*   **Decision:** Use ChromaDB for the local vector store.
*   **Rationale:** Runs entirely local/in-memory, integrates seamlessly with LangChain, and avoids the need for a cloud vector database subscription during development and interviews.

### LLM Provider (`langchain-openai`)
*   **Decision:** Use OpenAI (GPT-4o or `gpt-4o-mini`).
*   **Rationale:**
    *   Provides the most reliable function-calling/tool-calling capabilities required for an agentic router to decide between SQL and Vector tools.
    *   Excellent native support for `response_format={ "type": "json_object" }` and structured output parsing, which guarantees the agent returns data arrays and thought processes in a machine-readable format that LangGraph can easily route.

## 2. Unstructured Data Ingestion (Vector Search)

### True Semantic Chunking (`SemanticChunker`)
*   **Decision:** We are using LangChain's `SemanticChunker` (from `langchain-experimental`).
*   **Rationale:** `RecursiveCharacterTextSplitter` is *structural* chunking, not *semantic* chunking.
    *   **True Semantic Chunking** embeds every sentence and calculates the cosine distance between them. It groups sentences together into a chunk until the semantic meaning drastically shifts (a "breakpoint"), at which point it starts a new chunk.
    *   **Chunk Size:** Unlike structural splitter, there is **no fixed chunk size** (like 1000 characters). The chunk size is completely variable and is determined dynamically by the meaning of the text. If an architectural explanation is 3 sentences, the chunk is 3 sentences. If the explanation takes 15 sentences before moving to a new topic, the chunk is 15 sentences. You control the length indirectly by adjusting the breakpoint threshold (e.g., `breakpoint_threshold_type="percentile"`).
    *   **Fallback Limit:** We still combine this with a structural splitter as a fallback to enforce a hard maximum limit (e.g., 2000 characters) to protect LLM context windows in cases where a topic never shifts.
    *   **Why this matters:** Unlike arbitrary character limits which might split related thoughts, the `SemanticChunker` guarantees that all text within a chunk is contextually related. This significantly improves retrieval accuracy in RAG systems.

### Embedding Model (`OpenAIEmbeddings`)
*   **Decision:** We are using LangChain's default OpenAI embedding configuration, which resolves to high-dimensionality models (like `text-embedding-ada-002` or `text-embedding-3-small`).
*   **Rationale & Dimensionality Trade-offs:**
    *   **High Dimensionality (1536 dimensions):** OpenAI models generate 1536-dimensional vectors. This massive semantic space allows the model to capture highly complex, nuanced engineering concepts (e.g., the architectural differences between Kafka vs. RabbitMQ).
    *   **Compared to Low Dimensionality (e.g., 384 dimensions):** Smaller, local open-source models (like `all-MiniLM-L6-v2`) are much faster and cheaper to run, but they often collapse complex comparative topics into generic buckets (e.g., just "messaging systems"), reducing RAG accuracy for Staff-level architecture queries.
    *   **The Trade-off (Cost vs. Accuracy):** 1536-dimensional vectors take 4x the RAM and storage in a vector database compared to 384-dimensional vectors, and computing cosine distance at query time is mathematically heavier. For enterprise scale (millions of docs), this strictly increases cloud vector DB hosting costs.
    *   **Why Hosted OpenAI over Local Open-Source (e.g., BAAI/bge-large)?** While models like `bge-large` (1024 dimensions) often beat OpenAI on retrieval benchmarks and offer data privacy, hosting them locally requires PyTorch dependency management and hardware acceleration (GPUs). A reliable, hosted API eliminates that infrastructure complexity for this use case.
    *   *(Note: Newer models like OpenAI's `text-embedding-3` support "Matryoshka embeddings", allowing developers to truncate the 1536 dimensions down to 512 dimensions while retaining almost all accuracy, effectively solving the storage cost trade-off).*

### Deduplication via MD5 Hashing (UPSERT)
*   **Decision:** We calculate an MD5 hash of the raw document content, store it in chunk metadata, and compare hashes against the existing ChromaDB prior to running semantic splits or inserting embeddings.
*   **Rationale:** Standard vector databases do not natively prevent data duplication if the same scripts are run multiple times. If an ADR gets updated, doing a naively-appended embedding run will result in Chroma returning both the "old" meaning and the "new" meaning simultaneously to the LLM, causing hallucinations. By injecting document-level hashes, we implemented a custom true `UPSERT`. We skip unchanged files, and automatically delete old chunks for updated files before re-embedding them.
### Manual Metadata Injection for Hybrid Filtering
*   **Decision:** We are manually injecting a `document_type` metadata field (e.g., `adr` or `runbook`) into each parsed chunk based on its source folder.
*   **Rationale:** While vector search (Semantic Similarity) is excellent at retrieving contextually similar text, it is poor at exact-match filtering. By explicitly tagging the chunks in ChromaDB with structured metadata, we unlock **Hybrid Search**. This allows the Agent Router to later issue a targeted query like: *"Find me documents semantically similar to '504 timeout', but apply a hard filter where `metadata.document_type == 'runbook'`"* This vastly reduces LLM hallucination on large enterprise repositories.

## 3. Agent Architecture

### Single-Agent Router vs. Multi-Agent Systems
*   **Status:** Superseded by *Hybrid Triage-Routed Topology* below.
*   **Decision:** Use a single-agent router architecture instead of a multi-agent "supervisor" pattern.
*   **Rationale:**
    *   **Efficiency:** A single-agent router is more token-efficient and reduces latency by avoiding inter-agent communication overhead.
    *   **Iterative Reasoning:** The current router can already perform sequential tool calls (e.g., query SQL then Search Vector DB) within a single execution loop.
    *   **Complexity Management:** Multi-agent systems add significant orchestration complexity (managing handoffs, state merging, and specialized prompts). For the current scope of RAG and SQL retrieval, a single well-prompted agent is more robust and easier to maintain.
    *   **Future Proofing:** This single-agent approach is sufficient for the current simple use case. If the system grows to include significantly more tools or highly specialized domain logic, the architecture can be refactored into a multi-agent supervisor/worker pattern later.

### Hybrid Triage-Routed Topology (supersedes Single-Agent Router)
*   **Decision:** Replace the single-agent router with a triage-first supervisor graph (`src/agent.py`, helpers in `src/incident_workflow.py`). A `TriageResult` LLM call (`gpt-4o-mini.with_structured_output(TriageResult)`) classifies each user message as `incident`, `general`, or `out_of_scope`, then `route_target_for_mode` dispatches:
    *   **`incident`** → `structured_agent` (SQL-only tools) → `runbook_agent` (vector-search only) → `synthesize` node that composes the final incident brief from both sets of findings.
    *   **`general`** → `general_agent` — a single ReAct agent with all four tools (the original architecture, preserved for non-incident questions).
    *   **`out_of_scope`** → `decline_node`, a deterministic short-circuit that emits a fixed refusal with no LLM or tool call.
*   **Rationale:**
    *   **Narrower tool scope per node reduces hallucination.** During an active incident the structured node sees *only* SQL tools, so the LLM cannot "shortcut" to a documentation search before resolving the service and owner. The runbook node sees *only* `search_engineering_docs`, so it cannot fabricate metadata. In the prior single-agent design the same LLM held all four tools and would sometimes synthesise a runbook step before grounding the service identity.
    *   **Deterministic pipeline for the high-stakes path.** An on-call engineer needs the same structural answer every time: ownership → mitigation → evidence → gaps. A fixed `structured → runbook → synthesize` chain guarantees that structure rather than relying on ReAct loop convergence. The `SYNTHESIZE_SYSTEM_PROMPT` enforces the section layout (`## Summary / ## Ownership / ## Runbook / ## Evidence / ## Gaps`).
    *   **Triage absorbs the routing cost the original ADR was protecting against.** The original "efficiency" argument assumed every routing decision lived inside the ReAct loop. By doing one structured-output classification up front, we pay a single small LLM call to skip the entire incident chain for non-incident questions — net cheaper for the common general-question case than the old router that always loaded all four tool descriptions into context.
    *   **Out-of-scope is now a first-class branch.** The original ADR had no story for "weather / jokes / generic programming help" — the single agent would either decline via prompt instructions (unreliable) or burn tools trying. Triage's `out_of_scope` mode routes to a no-LLM `decline_node`, removing both cost and attack surface for off-topic input.
    *   **General questions keep the original simple loop.** The single-agent ReAct path is preserved as `general_agent` for ADR/design-rationale questions, where a fixed pipeline would be over-engineering. The supervisor only fires the multi-stage chain when triage labels the input `incident`.
    *   **Resilience built into triage.** When the triage LLM fails or returns unparseable output, `triage_node` defaults to `mode="general"` (see exception handler in `src/agent.py`). The system degrades to the original single-agent behaviour rather than declining the request, preserving availability.
    *   **Tradeoffs accepted:** Incident responses now make 3 LLM calls (structured + runbook + synthesize) plus triage, versus the original single ReAct loop. Latency and token cost both rise on the incident path, justified by the determinism and grounding gains above. State carries `structured_findings` and `runbook_findings` between nodes (see `AgentState` `TypedDict`), which is more graph state than the original router but is still small and serialisable.

### Retries and Backoff (OpenAI / Chroma)
*   **Status:** Superseded by *Bounded Retries via tenacity* below.
*   **Decision:** No retries or circuit breaker in the current demo; failures surface immediately to the user.
*   **Rationale:** Keeps the codebase simple for portfolio and local use. For production we would add: (1) **Retries with backoff** (e.g. `tenacity` or LangChain’s built-in retry) on transient OpenAI/network errors, with exponential backoff and a max attempt count; (2) **Circuit breaker** (e.g. `pybreaker` or a small state machine) around external calls so repeated failures stop hammering the API and allow partial degradation (e.g. SQL-only mode if Chroma is down). We would also consider timeouts and idempotency for write paths (e.g. vector upserts).

### Bounded Retries via tenacity (supersedes No-Retries stance)
*   **Decision:** Wrap direct LLM invocations (triage classification and incident-brief synthesis) in `_invoke_with_retry` (`src/agent.py`): `tenacity` retry with `stop_after_attempt(3)` and exponential backoff (1–8s), `reraise=True`, and `retry_if_not_exception_type((KeyboardInterrupt, SystemExit))` so user interrupts are never swallowed.
*   **Rationale:** Transient OpenAI errors (rate limits, connection resets) were the dominant failure mode in practice, and a bounded retry recovers most of them at negligible cost. Three attempts with capped backoff keeps worst-case added latency small and predictable. Failures after the final attempt still surface immediately, and `triage_node` additionally degrades to `mode="general"` on unrecoverable triage errors rather than declining the request.
*   **Still out of scope (deliberately):** a circuit breaker around external calls and retry coverage inside the prebuilt ReAct sub-agents (their tool-loop calls go through LangChain directly). Both remain documented production follow-ups; the demo favors simplicity over full resilience machinery.

### Observability (LangSmith)
*   **Decision:** Use LangSmith for tracing when configured via environment variables (`LANGSMITH_API_KEY`, `LANGSMITH_TRACING`, `LANGSMITH_PROJECT`). No application code changes are required; LangChain/LangGraph auto-instrument when these are set.
*   **Rationale:** LangSmith is the standard observability layer for the LangChain ecosystem. With `.env` (or `.env.example` copied to `.env`) populated, every agent run, tool call, and LLM request is traced to the configured project. This supports debugging, latency analysis, and token usage visibility without adding custom logging or metrics code. The template `.env.example` documents the optional variables; tracing is off if `LANGSMITH_API_KEY` is unset.

## 4. Guardrails & Safety

### Prompt Injection Detection (`protectai/deberta-v3-base-prompt-injection-v2`)
*   **Decision:** Detect prompt-injection attempts with ProtectAI's `deberta-v3-base-prompt-injection-v2` classifier, loaded through the `transformers` `text-classification` pipeline. The model ID and confidence threshold are config-driven (`EAC_PROMPT_INJECTION_MODEL`, default `protectai/deberta-v3-base-prompt-injection-v2`; `EAC_PROMPT_INJECTION_THRESHOLD`, default `0.85`). The check runs as a dedicated graph node (`prompt_injection_check`) between input validation and triage; flagged inputs short-circuit to `decline_node` without invoking the LLM or any tool. The detector fails open on load/runtime errors so a model-load failure does not take the whole agent down.
*   **Rationale:**
    *   **Why a classifier, not an LLM-as-judge?** An encoder-only DeBERTa-v3 model is discriminative — it maps text to a fixed label, with no token-generation head and no instruction-following surface. An LLM-based guard (e.g., asking `gpt-4o-mini` "is this an injection?") is itself susceptible to the very payload it inspects; a classifier is structurally immune. It also avoids an extra round-trip and per-message token cost.
    *   **Why DeBERTa-v3 over BERT / RoBERTa?** DeBERTa-v3 outperforms BERT and RoBERTa at the same parameter count on most GLUE/SuperGLUE classification benchmarks thanks to disentangled attention and improved relative position encoding. For a classification head over short (≤512-token) user prompts, that accuracy edge is essentially free at the same inference cost.
    *   **Why ProtectAI's fine-tune specifically?** ProtectAI publishes a maintained, current fine-tune (`-v2` denotes a refreshed training corpus). It is openly hosted on Hugging Face and loadable via `transformers.pipeline(...)` with no API key — consistent with the project's "runs entirely local, no cloud subscription" stance (see also: ChromaDB choice in §2). A peer fine-tune such as `deepset/deberta-v3-base-injection` is a drop-in alternative if benchmarks on this corpus ever favour it; swapping requires only flipping `EAC_PROMPT_INJECTION_MODEL`.
    *   **Why not regex / keyword heuristics?** Trivially bypassed by paraphrase, translation, or encoding. They produce a high false-negative rate against any adversary who has read the rules.
    *   **Why not commercial SaaS (Lakera Guard, Rebuff cloud)?** Strong products, but a paid API and network call would defeat the local/offline design goal and add a runtime dependency that interview environments cannot rely on.
    *   **Why not `LLM Guard` (ProtectAI's framework) or `Rebuff` (open-source)?** Both bundle multiple scanners (toxicity, PII, secrets, vector-DB of known attacks). Useful when those signals are needed, but they introduce heavier dependencies, more failure modes, and (for Rebuff) a vector store that must be maintained. We need exactly one signal — prompt-injection probability — so calling the underlying classifier directly is the smaller surface.
    *   **Why fail open?** A model-load or inference failure should degrade availability, not collapse the agent. The trade-off is explicit: an outage of the guard layer momentarily widens the attack surface, but the downstream agent still has SQL read-only enforcement, parameterised queries, and grounding instructions as defence-in-depth. A production deployment with stricter risk tolerance could flip this to fail closed by raising in the `except` branch of `detect_prompt_injection`.
    *   **Known gaps acknowledged:** The check runs on the latest user message only — multi-turn drip attacks across messages are not stitched together. It also runs on user input only, not on tool outputs, so *indirect* prompt injection embedded inside a retrieved ADR or runbook is not caught here; that risk is mitigated softly by the grounding system prompt and the read-only tool surface.

### SQL Read-Only Defense in Depth (SQLite URI `mode=ro`)
*   **Decision:** The agent-runtime SQLite connection in `get_sql_db()` (`src/agent.py`) is opened in read-only mode at the OS layer via the SQLite URI form `file:{path}?mode=ro`. The connection is plumbed through SQLAlchemy using a `creator` function that calls `sqlite3.connect(uri, uri=True, check_same_thread=False)` directly, rather than the `sqlite:///...` URL form. The ingestion pipeline (`scripts/setup`, `src/generate_mock_data.py`) is unaffected — it opens its own short-lived write-capable engine to seed the database.
*   **Rationale:**
    *   **Defense in depth against tool-boundary regress.** The primary write guard is the `_is_readonly_sql` regex check inside the `query_sql_database` tool, which rejects anything that isn't a single `SELECT` or `WITH` statement. That guard is correct today but is *only* a tool-boundary check — if a future contributor adds a new SQL tool and forgets the regex, writes succeed. Opening the connection itself in read-only mode makes writes structurally impossible regardless of which tool issues them. Verified empirically: a raw `db.run('DELETE FROM service_catalog')` against this connection raises `sqlite3.OperationalError: attempt to write a readonly database`.
    *   **Why URI `mode=ro` over `PRAGMA query_only=ON`?** Both block writes through the engine, but `mode=ro` is a *file-handle-level* restriction set at OS open, whereas `query_only` is a connection-session pragma that can be flipped off mid-session by anything that obtains a cursor. `mode=ro` also fails fast if the DB file is missing, which surfaces "you forgot to run `make setup`" immediately rather than silently creating an empty file. The agent process never legitimately writes, so the strictest guarantee is the right one.
    *   **Why the SQLAlchemy `creator` pattern over the `sqlite:///file:...?mode=ro` URL?** First attempt used `create_engine("sqlite:///file:{path}?mode=ro", connect_args={"uri": True})`. On Windows this failed with `OperationalError: unable to open database file` because SQLAlchemy's `sqlite:///` URL parser treated `file:C:/...` as a relative filesystem path and prepended the current working directory, producing a malformed `cwd + literal 'file:' + path` string before handing it to sqlite3. The `creator` callable receives no SQLAlchemy URL processing — the URI is passed verbatim to `sqlite3.connect()`. This is portable across OS path conventions and avoids drive-letter / leading-slash workarounds.
    *   **Tradeoff accepted:** The DB file must exist before `get_sql_db()` is first invoked. `make setup` already enforces this in normal flow, and the test fixture `seeded_sqlite` in `tests/test_guardrails.py` calls `generate_structured_data()` (and `close_connections()`) before any tool exercises the connection.
    *   **Test impact:** Zero regressions. The 43 tests in `tests/test_guardrails.py` continue to pass — the regex check at the tool boundary is still the first gate, and the OS-level guarantee is a redundant layer below it that the existing assertions never had to exercise directly.

## 5. Evaluation Strategy

### Golden Set v2: expected-source annotations and harder categories
*   **Decision:** Evolve `tests/eval/golden_set.json` from 50 to 103 examples with two backward-compatible optional fields, `expected_sources` (list of doc-ID stems the retriever must fetch) and `expected_not_found` (ground truth is absence of data), and two new categories: `negative` (nonexistent services/docs/teams; the correct answer is "not found") and `adversarial-scope` (out-of-scope requests dressed in PayLane vocabulary that must still be declined). The LangSmith dataset name bumps to `eac-copilot-golden-v2`; v1 is kept so historical experiments stay comparable within their own schema.
*   **Rationale:**
    *   **Stems, not paths.** `expected_sources` uses filename stems (e.g. `002-adopt-kafka-event-streaming`) because the same document lives at `docs/...` in dev and `tests/test_data/docs/...` in the sandbox; a path-based annotation would break depending on where the eval runs. Stems are unique across the corpus.
    *   **Negative cases catch confident hallucination.** A RAG agent that invents an owner for `cart-service` scores fine on keyword metrics; only an example whose reference facts state "this does not exist" exposes it.
    *   **Schema drift fails CI, not eval runs.** `scripts/validate_golden_set.py` (run as a plain unit test in `tests/eval/test_golden_set_schema.py`) checks unique IDs, known categories, and that every `expected_sources` stem resolves to a real file under `templates/mock_docs/`, so a corpus rename or annotation typo fails the build offline instead of surfacing mid-eval after spending API credits.

### Retrieval-quality evaluators: parse tool messages, don't plumb graph state
*   **Decision:** `retrieval_recall` and `retrieval_precision` (deterministic, free) compare `expected_sources` against the doc stems the agent actually retrieved. The retrieved stems are recovered by parsing `search_engineering_docs` ToolMessages with `src/citations.py`, which co-owns the tool-result header format (`format_doc_result`) and its parser (`extract_retrieved_sources`). The eval target returns them alongside the answer (`{"output", "retrieved_sources"}`).
*   **Rationale:** This cleanly separates *retrieval* failures (low recall: the RAG layer missed the doc) from *generation* failures (good recall but bad factuality: the LLM had the right context and still answered wrong), which is the diagnostic question every RAG regression starts with. Parsing the messages the graph already emits requires zero changes to production state or node wiring (no eval-only fields leak into `AgentState`), and keeping the format and parser in one module means they cannot drift apart.

### Guardrail red-team suite: pytest, not LangSmith; rates, not rows
*   **Decision:** `tests/eval/redteam_set.json` (~40 adversarial inputs + benign controls) runs through `tests/test_redteam_guardrails.py` as plain pytest. Assertions are **block-rates per attack family** (SQL families at 1.0 since the guard is deterministic; injection families at 0.8/0.75/0.5 for direct/roleplay/obfuscated) plus a **1.0 allow-rate on benign controls** as the false-positive guard. Adversarial cases that need an LLM to classify (scope probes) live in the golden set's `adversarial-scope` category instead.
*   **Rationale:** The guards under test (`_is_readonly_sql`, input validation, the DeBERTa classifier) are local, deterministic-ish, and free; pytest thresholds *are* the regression tracker, and putting them in LangSmith would add API-key friction for zero comparability gain. Rate-based assertions let known classifier misses stay in the dataset as the residual-risk record rather than being deleted to make tests green. The split rule is simple: LLM in the loop → LangSmith golden set; no LLM → pytest.

### Cost & latency: surface what LangSmith records, don't build a dashboard
*   **Decision:** `tests/eval/run_report.py` aggregates the rows `langsmith.evaluate()` returns (tokens, cost, p50/p95 latency, per-evaluator and per-category means), prints a table, and writes `eval_reports/eval_report.json` (uploaded as a CI artifact on manual eval runs). Nothing new is instrumented.
*   **Rationale:** LangSmith root runs already carry token counts, cost, and timing; building collection would duplicate it. Cross-commit comparison happens by diffing artifacts or in the LangSmith experiments UI. The one non-obvious fix shipped with this: the unit-test sandbox in `tests/conftest.py` applies to *every* pytest session (ancestor conftests load even for `pytest tests/eval/`), which would have silently pointed evals at the empty `tests/test_data/` corpus. `test_langsmith_eval.py` now removes the `EAC_*` overrides in a module-scoped fixture so evals always hit the real corpus.

## 6. Deployment & Service Layer

### FastAPI + SSE over a WebSocket or a plain JSON endpoint
*   **Decision:** Expose the compiled graph through FastAPI (`src/api/app.py`) with a single `POST /chat` endpoint that streams Server-Sent Events via `sse-starlette`. The stream is driven by `agent.astream(..., stream_mode=["updates", "messages"])` and filtered in a pure module (`src/api/sse.py`): `token` events are emitted only for user-facing nodes (`synthesize` and the `general_agent` subgraph, matched on `langgraph_node` / checkpoint-namespace metadata), while `node`, `tool_call`, `done`, and `error` events come from the `updates` channel. Event builders are dict-in/dict-out so they unit-test without a server.
*   **Rationale:**
    *   **SSE over WebSocket.** The chat flow is unidirectional server-push over a normal HTTP request; SSE needs no upgrade handshake, works through every proxy, and reconnects natively. A WebSocket would add a stateful protocol for no gain here.
    *   **Filter tokens at the boundary, not in the graph.** Internal triage and sub-agent token streams must not leak to the user. Filtering on stream metadata keeps the graph unchanged (no eval-only or API-only fields in `AgentState`) and keeps the format/parse logic in one testable module, mirroring the `src/citations.py` decision in §5.
    *   **Lifespan owns the singletons.** The graph is compiled once at startup into `app.state`; the injection classifier is warmed with one dummy call (skippable via `EAC_WARM_INJECTION_DETECTOR=0`) so the first real request doesn't pay model-load latency; `close_connections()` runs on shutdown. The existing lazy singletons in `src/agent.py` needed no change.

### Observability boundary: LangSmith for traces, Prometheus + JSON logs for the service
*   **Decision:** Keep LangSmith as the LLM/agent trace layer (unchanged, env-var auto-instrumented) and add only service-side signals in `src/api/observability.py`: structured JSON access logs with a per-request id (middleware), a Prometheus `/metrics` endpoint (`prometheus-fastapi-instrumentator`), and an `eac_guardrail_blocks_total` counter labeled by guardrail (`input-validation`, `prompt-injection`, `readonly-sql`, `out-of-scope`). `EAC_DEBUG=1` surfaces the LangSmith `run_id` in the `done` event to link a UI answer to its trace. No OpenTelemetry collector, Grafana, or Sentry.
*   **Rationale:** For a single-container demo those stacks are weight without signal; the defensible line is "LangSmith owns the LLM story, the service owns HTTP-level logs and metrics." The guardrail counter is the production-side mirror of the offline red-team suite (§5): the same layers that are threshold-tested get counted live. The boundary is stated so a reviewer sees a deliberate scope, not an omission.

### Docker: CPU-only torch, optional model bake, data as a mount
*   **Decision:** Single-stage `python:3.12-slim`. Install the CPU-only torch wheel *before* `requirements.txt` so pip never pulls the multi-GB CUDA build. A build arg `INSTALL_INJECTION_MODEL` (default `true`) bakes the DeBERTa classifier into `HF_HOME` for offline startup; CI builds with `false` to validate the image fast. Generated data (`chroma_db/`, SQLite, `docs/`) is never baked in: `docker-compose.yml` mounts it read-only from `./data`, with a `setup` profile service to generate it without host Python. Hugging Face Spaces instead commits the small fixed corpus into the Space repo (`deploy/huggingface.md`).
*   **Rationale:** Torch dominates the image size, so the CPU wheel is the single biggest win and the classifier stays in-process. Data is operator-specific (built with their OpenAI key) and must not ship in a public image. The `$PORT` env var lets the exact same image run locally (8000) and on Spaces (7860). Read-only mounts encode that the agent never writes to its data at runtime, consistent with the SQLite `mode=ro` stance in §4.

### langgraph.json: keep the factory stateless, let the platform own persistence
*   **Decision:** Ship `langgraph.json` pointing at `create_enterprise_copilot`, with `pyproject.toml` reading its runtime deps from `requirements.txt` (`dynamic = ["dependencies"]`) so `pip install .` and the platform install the same pinned set. The factory returns a graph with no checkpointer.
*   **Rationale:** LangGraph Platform injects its own persistence, so a checkpointer baked into the factory would conflict; a stateless factory also keeps the eval target and the FastAPI app free to choose their own (none for evals, per-session for the API in Phase C). One pinned dependency source avoids drift between the container, the platform, and local dev.
