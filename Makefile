# Auto-detect venv Python (Windows Scripts\ or Unix bin/); fall back to PATH python.
PYTHON := $(or $(wildcard venv/Scripts/python.exe),$(wildcard venv/bin/python),python)

.PHONY: help setup run serve test test-integration eval redteam lint format clean

help:
	@echo "Targets:"
	@echo "  setup             Validate env, generate mock data, build vector DB"
	@echo "  run               Start the interactive copilot"
	@echo "  serve             Start the FastAPI server (SSE chat API on :8000)"
	@echo "  dev-graph         Run the graph on LangGraph Platform dev server (langgraph dev)"
	@echo "  test              Run unit tests (no API key needed)"
	@echo "  test-integration  Run integration tests (requires OPENAI_API_KEY)"
	@echo "  eval              Run LangSmith evaluations"
	@echo "  redteam           Run the guardrail red-team suite (add -m integration for classifier rows)"
	@echo "  lint              Run ruff checks (lint + format check)"
	@echo "  format            Auto-fix lint issues and reformat"
	@echo "  clean             Remove generated docs/, engineering_data.db, chroma_db/"

setup:
	$(PYTHON) -m scripts.setup

run:
	$(PYTHON) main.py

serve:
	$(PYTHON) -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000

dev-graph:
	langgraph dev

test:
	$(PYTHON) -m pytest tests/ -v -m "not integration and not langsmith_eval"

test-integration:
	$(PYTHON) -m pytest tests/ -v -m "integration"

eval:
	$(PYTHON) -m pytest tests/eval/ -v -m langsmith_eval

redteam:
	$(PYTHON) -m pytest tests/test_redteam_guardrails.py -v -s

lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .

format:
	$(PYTHON) -m ruff check . --fix
	$(PYTHON) -m ruff format .

clean:
	$(PYTHON) -c "import shutil, os; [shutil.rmtree(p, ignore_errors=True) if os.path.isdir(p) else os.remove(p) for p in ['docs','chroma_db','tests/test_data'] if os.path.exists(p)]; [os.remove('engineering_data.db')] if os.path.exists('engineering_data.db') else None"
