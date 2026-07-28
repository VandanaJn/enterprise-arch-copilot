"""Single source of truth for project paths.

Env-controlled paths are exposed as functions so callers always read the
current environment value — no import-time freezing. Tests can set/monkeypatch
EAC_* vars in fixtures without worrying about when src.config was first imported.

Truly static paths (ROOT_DIR, TEMPLATES_DIR, DOC_SUBDIRS) remain module-level
constants because they never vary at runtime.
"""

from __future__ import annotations

import os

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# All subdirectory names under docs_dir() that hold ingestible markdown.
DOC_SUBDIRS = ("adrs", "runbooks", "postmortems", "design_docs")

TEMPLATES_DIR = os.path.join(ROOT_DIR, "templates", "mock_docs")


def docs_dir() -> str:
    return os.environ.get("EAC_DOCS_DIR", os.path.join(ROOT_DIR, "docs"))


def adr_dir() -> str:
    return os.path.join(docs_dir(), "adrs")


def runbook_dir() -> str:
    return os.path.join(docs_dir(), "runbooks")


def postmortem_dir() -> str:
    return os.path.join(docs_dir(), "postmortems")


def design_doc_dir() -> str:
    return os.path.join(docs_dir(), "design_docs")


def db_file() -> str:
    return os.environ.get("EAC_DB_FILE", os.path.join(ROOT_DIR, "engineering_data.db"))


def chroma_dir() -> str:
    return os.environ.get("EAC_CHROMA_DIR", os.path.join(ROOT_DIR, "chroma_db"))


def max_input_chars() -> int:
    return int(os.environ.get("EAC_MAX_INPUT_CHARS", "4000"))


def recursion_limit() -> int:
    return int(os.environ.get("EAC_RECURSION_LIMIT", "20"))


def prompt_injection_threshold() -> float:
    return float(os.environ.get("EAC_PROMPT_INJECTION_THRESHOLD", "0.85"))


def prompt_injection_model() -> str:
    return os.environ.get(
        "EAC_PROMPT_INJECTION_MODEL", "protectai/deberta-v3-base-prompt-injection-v2"
    )


def eval_report_path() -> str:
    return os.environ.get(
        "EAC_EVAL_REPORT_PATH", os.path.join(ROOT_DIR, "eval_reports", "eval_report.json")
    )


def debug_mode() -> bool:
    """When true, the API includes the LangSmith run id in SSE done events."""
    return os.environ.get("EAC_DEBUG", "0") == "1"


def rate_limit_per_minute() -> int:
    """Max POST /chat requests per client IP per minute; 0 disables the limiter."""
    return int(os.environ.get("EAC_RATE_LIMIT_PER_MIN", "0"))


def warm_injection_detector() -> bool:
    """When true, the API loads the injection classifier at startup (first-request latency)."""
    return os.environ.get("EAC_WARM_INJECTION_DETECTOR", "1") == "1"


def history_max_messages() -> int:
    """Max prior messages fed to an LLM per turn (bounds multi-turn token growth)."""
    return int(os.environ.get("EAC_HISTORY_MAX_MESSAGES", "20"))


def summarization_trigger_tokens() -> int:
    """Token count at which the general agent summarizes older turns."""
    return int(os.environ.get("EAC_SUMMARIZATION_TRIGGER_TOKENS", "3000"))


def summarization_keep_messages() -> int:
    """Recent messages the summarizer preserves verbatim when it compacts history."""
    return int(os.environ.get("EAC_SUMMARIZATION_KEEP_MESSAGES", "12"))


def context_edit_trigger_tokens() -> int:
    """Token count at which the incident sub-agents clear stale tool results."""
    return int(os.environ.get("EAC_CONTEXT_EDIT_TRIGGER_TOKENS", "6000"))


def context_edit_keep_tool_results() -> int:
    """Most recent tool results kept intact when context editing fires."""
    return int(os.environ.get("EAC_CONTEXT_EDIT_KEEP", "3"))
