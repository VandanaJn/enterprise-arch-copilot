# Auto-detect venv Python (Windows Scripts\ or Unix bin/); fall back to PATH python.
PYTHON := $(or $(wildcard venv/Scripts/python.exe),$(wildcard venv/bin/python),python)

.PHONY: help setup run test test-integration eval clean

help:
	@echo "Targets:"
	@echo "  setup             Validate env, generate mock data, build vector DB"
	@echo "  run               Start the interactive copilot"
	@echo "  test              Run unit tests (no API key needed)"
	@echo "  test-integration  Run integration tests (requires OPENAI_API_KEY)"
	@echo "  eval              Run LangSmith evaluations"
	@echo "  clean             Remove generated docs/, engineering_data.db, chroma_db/"

setup:
	$(PYTHON) -m scripts.setup

run:
	$(PYTHON) main.py

test:
	$(PYTHON) -m pytest tests/ -v -m "not integration and not langsmith_eval" --ignore=tests/eval

test-integration:
	$(PYTHON) -m pytest tests/ -v -m "integration" --ignore=tests/eval

eval:
	$(PYTHON) -m pytest tests/eval/ -v -m langsmith_eval

clean:
	$(PYTHON) -c "import shutil, os; [shutil.rmtree(p, ignore_errors=True) if os.path.isdir(p) else os.remove(p) for p in ['docs','chroma_db','tests/test_data'] if os.path.exists(p)]; [os.remove('engineering_data.db')] if os.path.exists('engineering_data.db') else None"
