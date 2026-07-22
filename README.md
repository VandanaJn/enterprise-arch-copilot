# Enterprise Architecture Copilot

A multi-agent RAG copilot that helps on-call engineers cut through internal docs and metadata during incidents. Built with **LangGraph**, **OpenAI**, **ChromaDB**, and **SQLite**: a triage-first supervisor topology, hybrid SQL + vector retrieval, MD5-based incremental embeddings, observability via LangSmith, a 103-example golden eval set with retrieval-quality and LLM-as-judge graders, and a red-team regression suite for the guardrails.

```
You: The /api/v1/checkout endpoint is failing with a 504. Who owns it and is there a runbook?
Copilot:
  ## Summary
  /api/v1/checkout (POST) belongs to checkout-service v3.2.0 — currently on tier-0 SLO.
  ## Ownership / paging
  Team Alpha — pagerduty-alpha
  ## Runbook / mitigation steps
  Per RB-001: check Datadog response-time spike, scale checkout-service replicas,
  verify Kafka consumer lag on checkout.events, restart connection pooler if RDS
  pool is exhausted. Page Team Alpha on-call if not mitigated within 5 minutes.
  ...
```

The fictional company **PayLane** (a payments-processing SaaS) is the data domain — see [templates/company_spec.md](templates/company_spec.md). The corpus (~50 ADRs, runbooks, postmortems, design docs) is **LLM-generated** from that spec.

---

## What this project demonstrates

- **Multi-agent orchestration with LangGraph.** A triage step routes incident-flavored questions through a structured-data agent → docs agent → synthesis chain; non-incident questions fall through to a single ReAct agent with all tools.
- **Retrieval-Augmented Generation done with care.** Semantic chunking via `SemanticChunker`, MD5 hash-based incremental upserts (no duplicate embeddings on rerun), and explicit `document_type` metadata for hybrid filtering.
- **Hybrid retrieval.** A single user query can cross both a SQLite service catalog and a Chroma vector store, with the agent deciding when each is needed.
- **Agent guardrails.** A layered defence-in-depth stack applied before any LLM call: input length + empty-message validation → ML-based prompt-injection detection (ProtectAI `deberta-v3-base-prompt-injection-v2`) → LLM triage with `out_of_scope` routing → tool-level SQL read-only enforcement and injection-safe parametrised queries.
- **Deployable service.** A FastAPI + SSE API ([src/api/](src/api/)) streams tokens and tool calls, with a Dockerfile (CPU-only torch), `langgraph.json` for LangGraph Platform, and a Hugging Face Spaces deploy guide.
- **Multi-turn memory.** A LangGraph checkpointer keeps per-thread conversation state, so follow-up questions resolve from context ("what is *their* on-call rotation?"); history is trimmed per turn and a per-turn state reset keeps a previously blocked thread usable.
- **Grounded citations.** Answers cite the exact runbook/ADR/postmortem they used as inline `[doc-id]` tags plus a Sources line, and a deterministic `citation_validity` evaluator flags any citation not backed by a retrieved document.
- **Observability.** LangSmith tracing for the LLM/agent layer; structured JSON logs, Prometheus `/metrics`, and guardrail-block counters for the service layer.
- **Evaluation.** Golden-set evals in `tests/eval/` use `langsmith.evaluate()`.
- **Resilience.** Tenacity-backed retry on LLM calls, narrowed exception handling, thread-safe lazy singletons for DB connections, and Windows-aware connection cleanup.
- **Honest test isolation.** Tests run against `tests/test_data/` — never the developer's real data directory. Running the full suite is non-destructive.

---

## Architecture

```
                    ┌──────────────────┐
   user msg ──────▶ │  validate_input  │  length cap · empty check
                    └────────┬─────────┘
              (rejected)─────┤
                             │ (ok)
                    ┌────────▼──────────────┐
                    │ prompt_injection_check │  ProtectAI DeBERTa v3
                    └────────┬──────────────┘
              (flagged) ─────┤
                             │ (clean)          ┌──────────────────┐
                    ┌────────▼─────────┐        │   decline_node   │
                    │      triage      │──────▶ │  (fixed message, │
                    └────────┬─────────┘        │   no LLM/tools)  │
      LLM structured output  │                  └──────────────────┘
      mode: incident | general | out_of_scope ──────────▲
                             │
           incident?─────────┴──────general?
               │                        │
               ▼                        ▼
   ┌───────────────────┐    ┌───────────────────────┐
   │  structured_agent │    │    general_agent       │
   │  (SQL tools only) │    │  (all 4 tools,         │
   └────────┬──────────┘    │   ReAct loop)          │
            ▼               └────────────┬───────────┘
   ┌───────────────────┐                 │
   │   runbook_agent   │                 │
   │  (vector search)  │                 │
   └────────┬──────────┘                 │
            ▼                            │
   ┌───────────────────┐                 │
   │    synthesize     │                 │
   │  (incident brief) │                 │
   └────────┬──────────┘                 │
            └───────────────┬────────────┘
                            ▼
                         response
```

Source: [src/agent.py](src/agent.py), helpers in [src/incident_workflow.py](src/incident_workflow.py).

---

## Guardrails

The agent applies four defence layers before any expensive LLM or tool call fires:

| Layer | Where | What it blocks |
|---|---|---|
| **Input validation** | `validate_input` node | Empty / whitespace-only messages; inputs exceeding `EAC_MAX_INPUT_CHARS` (default 4 000) |
| **Prompt-injection detection** | `prompt_injection_check` node | Injection attempts classified by [ProtectAI `deberta-v3-base-prompt-injection-v2`](https://huggingface.co/protectai/deberta-v3-base-prompt-injection-v2) — blocks when `label=INJECTION` and `score ≥ EAC_PROMPT_INJECTION_THRESHOLD` (default 0.85) |
| **Out-of-scope routing** | `triage` (LLM) + `decline_node` | Off-topic questions (weather, recipes, generic help) classified as `out_of_scope` by triage LLM → routed to a fixed-message decline node with no further tool or synthesis calls |
| **SQL safety** | `query_sql_database` / `query_incidents` tools + `get_sql_db()` connection | Two layers. **Tool boundary:** `query_sql_database` rejects non-SELECT/WITH statements, stacked queries, and comment-disguised writes; `query_incidents` uses parametrised SQLAlchemy `text()` queries with LIKE wildcard escaping. **Connection layer (defense in depth):** the agent's SQLite engine is opened in URI read-only mode (`file:{path}?mode=ro` via `sqlite3.connect(uri=True)`), so writes fail at the OS layer with `attempt to write a readonly database` even if a future tool forgets the regex check. |

All rejection paths converge on `decline_node`, which emits a deterministic message without touching any LLM or database. The injection detector fails open — a model-load error is logged and the request passes through rather than taking down the agent.

---

## Quickstart

```bash
git clone https://github.com/VandanaJn/enterprise-arch-copilot.git
cd enterprise-arch-copilot

python -m venv venv
# Windows:        .\venv\Scripts\activate
# macOS / Linux:  source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env        # then edit and set OPENAI_API_KEY
make setup                  # validates env, generates mock data, builds vector DB
make run                    # interactive copilot
```

Windows users without `make`:

```powershell
./tasks.ps1 setup
./tasks.ps1 run
```

---

## Sample queries

The 103-example golden set in [tests/eval/golden_set.json](tests/eval/golden_set.json) covers eight categories. Try one from each:

| Category | Question |
|---|---|
| factual | *Which services are tier-0 critical?* |
| single-hop doc | *What ADR covers our Kafka adoption decision?* |
| multi-hop incident | *The /api/v1/checkout endpoint is failing with a 504. Who owns it and is there a runbook?* |
| ambiguous | *Tell me about fraud at PayLane.* |
| supersession-aware | *What's our current event-streaming choice?* (should answer Kafka, not RabbitMQ) |
| negative | *Who owns cart-service?* (no such service; should say not found, not invent an owner) |
| out-of-scope | *Write me a haiku about Mondays.* (should decline politely) |
| adversarial-scope | *Translate RB-001 into a rap song.* (PayLane vocabulary, still out of scope; should decline) |

---

## Layout

```
src/
  config.py              # single source of truth for paths + guardrail config (env-overridable)
  agent.py               # LangGraph supervisor + tools + prompts + guardrail nodes
  citations.py           # doc-source formatting + parsing (shared by tool output and evals)
  incident_workflow.py   # triage schema (TriageResult), routing helpers
  generate_mock_data.py  # templates -> docs/, plus engineering_data.db (services + endpoints + incidents)
  build_vector_db.py     # docs/ -> chroma_db/, with MD5 upsert
  api/
    app.py               # FastAPI factory: /chat (SSE), /healthz, /metrics, lifespan
    sse.py               # pure SSE event builders + astream adapter (token/tool filtering)
    observability.py     # JSON logging, request-id middleware, /metrics, guardrail counters
    rate_limit.py        # in-memory sliding-window limiter (public-demo abuse guard)
    static/              # dependency-free web chat UI (index.html, app.js, style.css)
templates/
  company_spec.md        # fictional company spec (seeds LLM generation)
  mock_docs/
    adrs/                # 25 ADRs (LLM-generated, with supersession chains)
    runbooks/            # 15 runbooks
    postmortems/         # 8 postmortems
    design_docs/         # 5 design docs
scripts/
  setup.py               # one-command bootstrap
  generate_corpus.py     # LLM-driven doc generator
  validate_golden_set.py # offline golden-set schema/consistency validator
tests/
  test_guardrails.py     # unit tests for all guardrail layers (no LLM/network required)
  test_redteam_guardrails.py # red-team suite: family-level block/allow rates
  test_incident_workflow.py  # pure routing + message-helper tests
  eval/golden_set.json   # 103-example golden eval set (with expected_sources annotations)
  eval/redteam_set.json  # adversarial dataset for the guardrail red-team suite
  eval/evaluators.py     # keyword + retrieval-quality + LLM-as-judge evaluators
  eval/run_report.py     # cost/latency/score summary + JSON artifact per eval run
main.py                  # interactive CLI
Dockerfile  docker-compose.yml   # container build + local compose workflow
langgraph.json           # LangGraph Platform graph manifest
deploy/huggingface.md    # Hugging Face Spaces deploy guide
Makefile  tasks.ps1      # task runners
```

Generated artifacts (`docs/`, `engineering_data.db`, `chroma_db/`) are gitignored — `templates/` is the canonical source. Re-run `make setup` after editing templates.

---

## Configuration

`.env` (copy from `.env.example`):

| Var | Required | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | yes | Chat + embeddings |
| `LANGSMITH_API_KEY` | optional | Tracing |
| `LANGSMITH_TRACING` | optional | `true` to enable tracing |
| `LANGSMITH_PROJECT` | optional | Project name in LangSmith |

Optional path overrides (rarely needed; tests use these):

| Var | Default |
|---|---|
| `EAC_DOCS_DIR` | `<repo>/docs` |
| `EAC_DB_FILE` | `<repo>/engineering_data.db` |
| `EAC_CHROMA_DIR` | `<repo>/chroma_db` |
| `EAC_GENERATION_MODEL` | `gpt-4o` (used by `scripts/generate_corpus.py`) |
| `EAC_EVAL_QUICK` | unset (set to `1` for CI-friendly subset eval) |
| `EAC_EVAL_MIN_SCORE` | `0.5` (per-evaluator floor for eval acceptance) |
| `EAC_EVAL_RETRIEVAL_MIN` | `0.6` (floor for `retrieval_recall` mean) |
| `EAC_EVAL_CITATION_MIN` | `0.8` (floor for `citation_validity` mean when any answer cites) |
| `EAC_EVAL_DECLINE_MIN` | `0.9` (floor for declines on out-of-scope + adversarial-scope) |
| `EAC_EVAL_REPORT_PATH` | `eval_reports/eval_report.json` (per-run cost/latency/score artifact) |

Guardrail tuning:

| Var | Default | Purpose |
|---|---|---|
| `EAC_MAX_INPUT_CHARS` | `4000` | Maximum user message length before rejection |
| `EAC_RECURSION_LIMIT` | `20` | LangGraph max node visits per run (fail-fast on runaway loops) |
| `EAC_PROMPT_INJECTION_THRESHOLD` | `0.85` | Minimum confidence score to block as injection |
| `EAC_PROMPT_INJECTION_MODEL` | `protectai/deberta-v3-base-prompt-injection-v2` | HuggingFace model ID for the injection classifier |

API service tuning:

| Var | Default | Purpose |
|---|---|---|
| `PORT` | `8000` | Port the server listens on (Spaces sets `7860`) |
| `EAC_RATE_LIMIT_PER_MIN` | `0` (off) | Max `POST /chat` requests per client IP per minute |
| `EAC_DEBUG` | `0` | `1` includes the LangSmith `run_id` in the SSE `done` event |
| `EAC_WARM_INJECTION_DETECTOR` | `1` | Load the injection classifier at startup vs. lazily |
| `EAC_HISTORY_MAX_MESSAGES` | `20` | Max prior messages fed to an LLM per turn (multi-turn context bound) |

---

## How the data was made

The fictional engineering organization (**PayLane**) is described in a single source-of-truth file at [templates/company_spec.md](templates/company_spec.md): 10 services, 5 teams, a tech stack, a 6-year engineering timeline, and cross-reference rules.

The 50+ markdown documents in `templates/mock_docs/` are **LLM-generated from that spec** by [scripts/generate_corpus.py](scripts/generate_corpus.py). The script reads the spec into the system prompt, lists already-generated docs to avoid duplicates, and uses `gpt-4o` with structured output (Pydantic) to produce well-formed YAML frontmatter (`id`, `status`, `date`, `services`, `supersedes`, etc.) plus a markdown body. Generation is idempotent — re-running skips existing IDs unless `--force` is passed.

```bash
python -m scripts.generate_corpus --type adrs --count 25
python -m scripts.generate_corpus --type runbooks --count 15
python -m scripts.generate_corpus --type adrs --id ADR-007 --force --topic "..."  # regenerate one
```

This approach scales to a portfolio-credible corpus quickly while keeping the entire dataset reproducible from the spec — every reviewer can regenerate it themselves to confirm.

---

## Evaluation

Real RAG systems live or die by their evals. The harness in [tests/eval/](tests/eval/) runs each commit against a 103-example golden set with seven evaluators:

| Evaluator | Type | Score | What it measures |
|---|---|---|---|
| `keyword_coverage` | deterministic | 0.0–1.0 | Fraction of expected keywords present in the answer |
| `retrieval_recall` | deterministic | 0.0–1.0 | Fraction of `expected_sources` docs the agent actually retrieved |
| `retrieval_precision` | deterministic | 0.0–1.0 | Fraction of retrieved docs that were expected |
| `citation_validity` | deterministic | 0.0–1.0 | Fraction of the answer's inline `[doc-id]` citations backed by a retrieved doc |
| `factuality` | LLM-as-judge (`gpt-4o`) | 0 / 0.5 / 1 | Agreement with `reference_facts` |
| `groundedness` | LLM-as-judge (`gpt-4o`) | 0 / 0.5 / 1 | Uses concrete PayLane entities (services, ADR IDs) vs. generic content |
| `appropriate_decline` | LLM-as-judge (`gpt-4o`) | 0 / 1 | For out-of-scope questions, did the agent decline politely? |

The retrieval evaluators compare the doc-ID stems the agent retrieved (parsed from tool messages by [src/citations.py](src/citations.py)) against per-example `expected_sources` annotations, so a bad answer can be attributed to *retrieval* (low recall) vs. *generation* (good recall, bad factuality).

Categories in the golden set:

| Category | Examples | Purpose |
|---|---|---|
| factual lookups | 12 | SQL retrieval precision (versions, owners, languages, tiers) |
| single-hop docs | 22 | Vector retrieval accuracy (which ADR covers X?) |
| multi-hop incident | 27 | Supervisor graph: SQL → docs → synthesis |
| ambiguous / partial | 11 | Fuzzy matching, partial service names |
| supersession-aware | 9 | Following `supersedes`/`superseded_by` chains |
| negative | 10 | Ground truth is absence; agent must say "not found", not hallucinate |
| out-of-scope | 4 | Polite refusal of off-topic questions |
| adversarial-scope | 8 | Off-topic requests dressed in PayLane vocabulary; must still decline |

The dataset is uploaded to LangSmith as a **persistent named dataset** (`eac-copilot-golden-v2`; v1 kept for historical experiments) so experiments across commits are directly comparable in the LangSmith UI. [scripts/validate_golden_set.py](scripts/validate_golden_set.py) runs as a plain unit test in CI, so schema drift (typo'd category, dangling `expected_sources` after a corpus rename) fails the build.

Each run also writes a cost/latency/score report (`eval_reports/eval_report.json`: tokens, dollars, p50/p95 latency, per-category means) surfaced from data LangSmith already records.

```bash
make eval                          # full run, ~103 examples × 6 evaluators (a few $ OpenAI)
EAC_EVAL_QUICK=1 make eval         # 2 per category × deterministic evaluators only (CI-friendly)
```

### Guardrail red-team suite

[tests/eval/redteam_set.json](tests/eval/redteam_set.json) holds ~40 adversarial inputs (SQL writes, stacked statements, comment-disguised writes, oversize input, direct/roleplay/obfuscated prompt injection) plus benign controls. [tests/test_redteam_guardrails.py](tests/test_redteam_guardrails.py) asserts **block-rates per attack family** (misses stay in the dataset as the residual-risk record) and a **100% allow-rate on benign controls** (false-positive guard). SQL and validation gates run in normal CI; the injection classifier rows run under the `integration` marker.

```bash
make redteam                       # SQL + validation gates (pure, fast)
pytest tests/test_redteam_guardrails.py -s   # all gates incl. DeBERTa classifier
```

---

## Testing

```bash
make test               # unit tests, no API key needed
make test-integration   # hits OpenAI; runs against tests/test_data/
make eval               # LangSmith golden-set evals
```

Tests are sandboxed under `tests/test_data/`. Running the suite never touches your dev `engineering_data.db`, `docs/`, or `chroma_db/`. The `tests/conftest.py` fixture sets the `EAC_*` env vars before any `src.*` import, so the sandbox is invisible to the production code path.

---

## Deployment

The agent is exposed as a FastAPI service ([src/api/](src/api/)) that streams responses over Server-Sent Events. The compiled graph, the guardrails, the injection classifier, and the on-disk data stores all run in one process; the only runtime dependency is the OpenAI API.

**Run locally:**

```bash
make serve                 # uvicorn on http://127.0.0.1:8000
```

Open `http://127.0.0.1:8000/` for the **web chat UI** (a dependency-free static page served by the API): streamed answers, tool-call chips, `[doc-id]` citation highlights, and multi-turn history restored from the thread. The raw endpoints are below if you prefer curl.

```bash
# stream an incident brief (SSE): node -> tool_call -> token -> done events
curl -N -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"The /api/v1/checkout endpoint is throwing 504s. Who owns it and is there a runbook?"}'
```

Endpoints: `POST /chat` (SSE; `{message, thread_id?}`, server mints a `thread_id` when omitted), `GET /threads/{id}/messages` (transcript for restore), `GET /healthz` (503 until the data files exist), `GET /metrics` (Prometheus), `GET /` (web chat UI).

**Docker** (CPU-only torch; data lives under `./data`, mounted read-only):

```bash
docker compose run --rm setup   # generate data/ (no host Python needed)
docker compose up               # serve on http://localhost:8000
```

**LangGraph Platform**: [langgraph.json](langgraph.json) exposes the graph factory, so `langgraph dev` (free Developer tier, self-hosted) runs it with LangGraph Studio and the [Agent Chat UI](https://github.com/langchain-ai/agent-chat-ui) out of the box. Install the CLI in a separate venv (`pip install "langgraph-cli[inmem]"`); it pins an older `sse-starlette` than the API uses, so it is deliberately not in `requirements-dev.txt`.

**Hosted demo**: a manual GitHub Actions workflow ([`deploy-hf.yml`](.github/workflows/deploy-hf.yml)) deploys the same image to a private Hugging Face Docker Space. It generates the corpus in CI (cached, so unchanged deploys cost nothing), bakes it into the image, and provisions the Space's secret and port variable. See [deploy/huggingface.md](deploy/huggingface.md) for the required secrets/variable and how to flip the Space public. `EAC_RATE_LIMIT_PER_MIN` caps API spend once it is public.

---

## Observability

**LLM/agent traces**: when `LANGSMITH_API_KEY` and `LANGSMITH_TRACING=true` are set, LangChain/LangGraph auto-instrument every node, tool call, and token cost under the project named by `LANGSMITH_PROJECT`. With `EAC_DEBUG=1` the API also returns the LangSmith `run_id` in the SSE `done` event.

**Service layer**: the API emits structured JSON access logs with a per-request id, exposes Prometheus metrics at `/metrics` (latency histograms, request/error counts), and increments an `eac_guardrail_blocks_total` counter labeled by which guardrail fired (`input-validation`, `prompt-injection`, `readonly-sql`, `out-of-scope`). That counter is the production-side mirror of the offline red-team suite. The boundary is deliberate: LangSmith owns the LLM traces, the service owns logs and metrics; no OTel collector or Grafana stack for a single-container demo.

---

## Troubleshooting

**`Could not connect to tenant default_tenant`** — your `chroma_db/` is empty, partial, or from a different ChromaDB version. Run `make clean && make setup`.

**File-locked errors on Windows when deleting `chroma_db/`** — exit any running copilot process; `close_connections()` releases the SQLAlchemy engine and ChromaDB handle.

**CI / `.github/workflows/ci.yml`** — lint (ruff) and unit tests run on every push/PR. The LangSmith eval job is **manual**: trigger it from Actions → CI → *Run workflow* with `run_eval` checked, after configuring `OPENAI_API_KEY` and `LANGSMITH_API_KEY` as repository secrets. It runs the quick-mode eval and uploads `eval_reports/` as a build artifact.
