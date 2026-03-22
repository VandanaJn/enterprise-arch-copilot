# Enterprise Architecture Copilot

This project is an advanced Retrieval-Augmented Generation (RAG) system built with LangChain, LangGraph, and OpenAI embeddings. It simulates an AI engineering assistant capable of querying internal enterprise documentation (ADRs, runbooks) and structured metadata (service catalog, API endpoints) via SQLite and ChromaDB.

## Project Features

* **Data Generation**: Procedurally creates rich mock Architectural Decision Records (ADRs), runbooks, and a relational service catalog.
* **Semantic Chunking**: Employs LangChain's `SemanticChunker` to semantically divide raw markdown documentation.
* **Hybrid Search Ready**: Injects unstructured documents with explicit metadata (e.g. `document_type: adr`) for targeted exact-match filtering alongside semantic similarity.
* **Idempotent Vector Insertion**: Implements a custom UPSERT strategy utilizing MD5 document hashing to guarantee the vector database is only populated with updated or new chunks, preventing hallucinations caused by duplications on rerun.
* **Incident-first supervisor graph**: LangGraph triage routes *incident* questions through SQL-only and vector-only sub-agents, then synthesizes an incident brief; other questions use a single agent with all tools (see `project_specification.md`).

## Project Structure
- `templates/mock_docs/`: **Source** markdown for ADRs and runbooks (edit here). Not ingested directly by the embedder.
- `src/`: Core Python application logic and agents.
  - `agent.py`: Supervisor graph, tools, and prompts.
  - `incident_workflow.py`: Triage schema and pure helpers (unit-tested).
  - `generate_mock_data.py`: Copies templates into `docs/`, creates `engineering_data.db`.
  - `build_vector_db.py`: Reads `docs/`, chunks and embeds into `chroma_db/`.
- `main.py`: Interactive CLI — run after mock data and vector DB are built.
- `tests/`: Pytest suite (unit + integration).
  - `tests/eval/`: LangSmith `evaluate()` golden-set tests (`langsmith` is listed in `requirements.txt`).
- `tests/conftest.py`: Adds the repo root to `sys.path`, loads repo-root `.env`, session teardown for DB connections.
- `DECISIONS.md`: Architectural decisions log.

*Note: Generated artifacts (`docs/`, `chroma_db/`, `engineering_data.db`) are gitignored—do not treat `docs/` as the canonical copy of markdown; change templates and regenerate.*

### Data pipeline

1. **Templates** (`templates/mock_docs/adrs`, `.../runbooks`) hold the real ADR/runbook text.  
2. **`generate_mock_data.py`** copies them to **`docs/`** and (re)builds **`engineering_data.db`**.  
3. **`build_vector_db.py`** reads **`docs/`** and writes **`chroma_db/`** (embeddings).  

After you change any file under `templates/mock_docs/`, run steps 2–3 again so `docs/` and Chroma stay in sync.

**Windows:** If deleting `chroma_db/` or `engineering_data.db` fails (“file in use”), exit any Python session using the app or call `close_connections()` from `src.agent`, then retry.

**ChromaDB “Could not connect to tenant default_tenant”:** Your `chroma_db/` directory is often empty, partial, or from a different ChromaDB version. Quit the copilot, delete `chroma_db/`, run `python src/build_vector_db.py` again (after `generate_mock_data` so `docs/` exists). If it still fails, reinstall deps: `pip install -r requirements.txt`.

## Setup Instructions

1. **Clone the repository:**
   ```bash
   git clone https://github.com/VandanaJn/enterprise-arch-copilot.git
   cd enterprise-arch-copilot
   ```

2. **Set up a Python virtual environment:**
   ```bash
   python -m venv venv
   
   # Windows
   .\venv\Scripts\activate
   
   # macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
   This includes `langchain`, `chromadb`, `pytest`, and `langsmith` (for offline evals in `tests/eval/`).

4. **Configure environment:**
   Copy `.env.example` to `.env` and set your keys:
   ```bash
   cp .env.example .env
   ```
   Then edit `.env` and set at least:
   - `OPENAI_API_KEY` — required for the copilot, embeddings, and integration tests.
   Optional for [LangSmith](https://smith.langchain.com) observability (traces, latency, tool calls):
   - `LANGSMITH_API_KEY`
   - `LANGSMITH_TRACING=true`
   - `LANGSMITH_PROJECT=enterprise-arch-copilot`

## Usage

**Step 1: Generate Mock Data**
```bash
python src/generate_mock_data.py
```
This generates a `docs/` folder containing dummy ADRs and Runbooks, and initializes an `engineering_data.db` SQLite database.

**Step 2: Build the Vector Database**
```bash
python src/build_vector_db.py
```
This script processes the markdown files, calculates their hashes, transforms them recursively into chunks, and stores their embeddings in a local `chroma_db/` directory.

**Step 3: Run the copilot (interactive)**
```bash
python main.py
```
Type `exit` or `quit` to leave the chat loop.

## Running Tests

**Quick run (no API key or built DB required)** — runs unit tests only (e.g. data generation, chunking, metadata):
```bash
pytest tests/ -v -m "not integration and not langsmith_eval"
```

**Full test suite** — integration tests need `OPENAI_API_KEY` and a built vector DB. One-time setup:
1. Set `OPENAI_API_KEY` in your `.env` file.
2. Generate mock data and build the vector DB:
   ```bash
   python src/generate_mock_data.py
   python src/build_vector_db.py
   ```
3. Run all tests:
   ```bash
   pytest tests/ -v
   ```

Integration tests (agent routing, vector search, Chroma connectivity) are marked with `@pytest.mark.integration` and are skipped when the API key is missing or when `chroma_db/` does not exist.

### LangSmith evaluations (offline)

Golden-set evaluations use LangSmith’s [`evaluate()`](https://docs.smith.langchain.com/evaluation) API (same pattern as the *Intro to LangSmith* course: target function + row evaluators). They live under `tests/eval/`, are marked `@pytest.mark.langsmith_eval`, and are **skipped** unless `OPENAI_API_KEY`, `LANGSMITH_API_KEY`, `engineering_data.db`, and `chroma_db/` are all present. `tests/conftest.py` loads `.env` from the **repository root** (next to `README.md`) before tests import `src.*`, regardless of pytest’s working directory.

After mock data and the vector DB are built:

```bash
pytest tests/eval/ -v -m langsmith_eval
```

Optional: `EAC_EVAL_MIN_SCORE` (default `0.5`) sets the minimum acceptable `keyword_coverage` score per example.

**CI:** `.github/workflows/ci.yml` runs unit tests on every push/PR, then runs the LangSmith eval job when the workflow has access to secrets (same-repo PRs and pushes). Configure repository secrets `OPENAI_API_KEY` and `LANGSMITH_API_KEY`. If either secret is missing, the eval step exits successfully without running tests (so CI stays green). Eval traces go to the project named by `LANGSMITH_PROJECT` (the workflow sets `enterprise-arch-copilot-eval`).

## Observability (LangSmith)

When `LANGSMITH_API_KEY` and `LANGSMITH_TRACING=true` are set in `.env`, LangChain/LangGraph automatically send traces to [LangSmith](https://smith.langchain.com). You can inspect runs, latency, tool calls, and token usage in the project named by `LANGSMITH_PROJECT` (e.g. `enterprise-arch-copilot`). No code changes are required beyond loading `.env`; the framework instruments calls when these variables are present.