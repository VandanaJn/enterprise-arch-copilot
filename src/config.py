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
