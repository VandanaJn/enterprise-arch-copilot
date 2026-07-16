<#
.SYNOPSIS
    Cross-platform-friendly task runner for the Enterprise Architecture Copilot.

.DESCRIPTION
    PowerShell equivalent of the Makefile, for Windows users who do not have
    `make` installed. Run from the repo root:

        ./tasks.ps1 setup
        ./tasks.ps1 run
        ./tasks.ps1 test
        ./tasks.ps1 test-integration
        ./tasks.ps1 eval
        ./tasks.ps1 clean
#>

param(
    [Parameter(Position = 0)]
    [ValidateSet("help", "setup", "run", "serve", "test", "test-integration", "eval", "redteam", "lint", "format", "clean")]
    [string]$Task = "help"
)

$ErrorActionPreference = "Stop"

# Prefer the project venv if present; otherwise fall back to PATH `python`.
$venvPython = Join-Path $PSScriptRoot "venv\Scripts\python.exe"
if (Test-Path $venvPython) {
    $Python = $venvPython
} else {
    $Python = "python"
}

switch ($Task) {
    "help" {
        @"
Targets:
  setup             Validate env, generate mock data, build vector DB
  run               Start the interactive copilot
  serve             Start the FastAPI server (SSE chat API on :8000)
  test              Run unit tests (no API key needed)
  test-integration  Run integration tests (requires OPENAI_API_KEY)
  eval              Run LangSmith evaluations
  redteam           Run the guardrail red-team suite
  lint              Run ruff checks (lint + format check)
  format            Auto-fix lint issues and reformat
  clean             Remove generated docs/, engineering_data.db, chroma_db/
"@
    }
    "setup"            { & $Python -m scripts.setup }
    "run"              { & $Python main.py }
    "serve"            { & $Python -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000 }
    "test"             { & $Python -m pytest tests/ -v -m "not integration and not langsmith_eval" }
    "test-integration" { & $Python -m pytest tests/ -v -m "integration" }
    "eval"             { & $Python -m pytest tests/eval/ -v -m langsmith_eval }
    "redteam"          { & $Python -m pytest tests/test_redteam_guardrails.py -v -s }
    "lint"             { & $Python -m ruff check .; if ($?) { & $Python -m ruff format --check . } }
    "format"           { & $Python -m ruff check . --fix; & $Python -m ruff format . }
    "clean" {
        foreach ($p in @("docs", "chroma_db", "engineering_data.db", "tests/test_data")) {
            if (Test-Path $p) {
                Remove-Item -Recurse -Force $p
                Write-Host "Removed $p"
            }
        }
    }
}
