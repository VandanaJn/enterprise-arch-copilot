# Enterprise Architecture Copilot

A multi-agent RAG copilot that helps on-call engineers cut through internal docs and metadata during incidents. Built with **LangGraph**, **OpenAI**, **ChromaDB**, and **SQLite** — with a triage-first supervisor topology, hybrid SQL + vector retrieval, MD5-based incremental embeddings, observability via LangSmith, and a 50-example golden eval set with LLM-as-judge graders.

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
- **Observability.** Optional LangSmith tracing — every node, tool call, and token cost is captured.
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

The 50-example golden set in [tests/eval/golden_set.json](tests/eval/golden_set.json) covers six categories. Try one from each:

| Category | Question |
|---|---|
| factual | *Which services are tier-0 critical?* |
| single-hop doc | *What ADR covers our Kafka adoption decision?* |
| multi-hop incident | *The /api/v1/checkout endpoint is failing with a 504. Who owns it and is there a runbook?* |
| ambiguous | *Tell me about fraud at PayLane.* |
| supersession-aware | *What's our current event-streaming choice?* (should answer Kafka, not RabbitMQ) |
| out-of-scope | *Write me a haiku about Mondays.* (should decline politely) |

---

## Layout

```
src/
  config.py              # single source of truth for paths + guardrail config (env-overridable)
  agent.py               # LangGraph supervisor + tools + prompts + guardrail nodes
  incident_workflow.py   # triage schema (TriageResult), routing helpers
  generate_mock_data.py  # templates -> docs/, plus engineering_data.db (services + endpoints + incidents)
  build_vector_db.py     # docs/ -> chroma_db/, with MD5 upsert
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
tests/
  test_guardrails.py     # unit tests for all guardrail layers (no LLM/network required)
  test_incident_workflow.py  # pure routing + message-helper tests
  eval/golden_set.json   # 50-example golden eval set
  eval/evaluators.py     # keyword + LLM-as-judge evaluators
main.py                  # interactive CLI
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

Guardrail tuning:

| Var | Default | Purpose |
|---|---|---|
| `EAC_MAX_INPUT_CHARS` | `4000` | Maximum user message length before rejection |
| `EAC_RECURSION_LIMIT` | `20` | LangGraph max node visits per run (fail-fast on runaway loops) |
| `EAC_PROMPT_INJECTION_THRESHOLD` | `0.85` | Minimum confidence score to block as injection |
| `EAC_PROMPT_INJECTION_MODEL` | `protectai/deberta-v3-base-prompt-injection-v2` | HuggingFace model ID for the injection classifier |

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

Real RAG systems live or die by their evals. The harness in [tests/eval/](tests/eval/) runs each commit against a 50-example golden set with four evaluators:

| Evaluator | Type | Score | What it measures |
|---|---|---|---|
| `keyword_coverage` | deterministic | 0.0–1.0 | Fraction of expected keywords present in the answer |
| `factuality` | LLM-as-judge (`gpt-4o`) | 0 / 0.5 / 1 | Agreement with `reference_facts` |
| `groundedness` | LLM-as-judge (`gpt-4o`) | 0 / 0.5 / 1 | Uses concrete PayLane entities (services, ADR IDs) vs. generic content |
| `appropriate_decline` | LLM-as-judge (`gpt-4o`) | 0 / 1 | For out-of-scope questions, did the agent decline politely? |

Categories in the golden set:

| Category | Examples | Purpose |
|---|---|---|
| factual lookups | 12 | SQL retrieval precision (versions, owners, languages, tiers) |
| single-hop docs | 12 | Vector retrieval accuracy (which ADR covers X?) |
| multi-hop incident | 12 | Supervisor graph: SQL → docs → synthesis |
| ambiguous / partial | 6 | Fuzzy matching, partial service names |
| supersession-aware | 4 | Following `supersedes`/`superseded_by` chains |
| out-of-scope | 4 | Polite refusal of off-topic questions |

The dataset is uploaded to LangSmith as a **persistent named dataset** (`eac-copilot-golden-v1`) so experiments across commits are directly comparable in the LangSmith UI.

```bash
make eval                          # full run, ~50 examples × 4 evaluators (~$1-2 OpenAI)
EAC_EVAL_QUICK=1 make eval         # ~12 examples × keyword_coverage only (CI-friendly)
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

## Observability

When `LANGSMITH_API_KEY` and `LANGSMITH_TRACING=true` are set, LangChain/LangGraph automatically push traces to [LangSmith](https://smith.langchain.com). You can inspect every node, tool call, and token cost under the project named by `LANGSMITH_PROJECT`.

---

## Troubleshooting

**`Could not connect to tenant default_tenant`** — your `chroma_db/` is empty, partial, or from a different ChromaDB version. Run `make clean && make setup`.

**File-locked errors on Windows when deleting `chroma_db/`** — exit any running copilot process; `close_connections()` releases the SQLAlchemy engine and ChromaDB handle.

**CI / `.github/workflows/ci.yml`** — unit tests run on every push/PR; the LangSmith eval job runs only when both `OPENAI_API_KEY` and `LANGSMITH_API_KEY` repository secrets are configured.
