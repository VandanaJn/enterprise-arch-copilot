"""Source formatting and parsing for retrieved documents.

The tool-result header format and its parser live in one module so they can
never drift apart: `search_engineering_docs` formats results with
`format_doc_result`, and eval/citation code recovers the sources with
`extract_retrieved_sources`. Pure functions, no I/O, no LLM.
"""

from __future__ import annotations

import re
from typing import Any

SEARCH_DOCS_TOOL_NAME = "search_engineering_docs"

_SOURCE_HEADER_TEMPLATE = "--- Document {n} (Type: {doc_type}, Source: {source}) ---"
_SOURCE_HEADER_RE = re.compile(r"^--- Document \d+ \(Type: .*?, Source: (.*?)\) ---$", re.MULTILINE)


def source_stem(path: str) -> str:
    """Filename without directory or extension, tolerant of / and \\ separators.

    Stems (not full paths) are the stable document identifier: the same doc lives
    under docs/... in dev and tests/test_data/docs/... in the test sandbox.
    """
    name = path.replace("\\", "/").rsplit("/", 1)[-1]
    return name.rsplit(".", 1)[0] if "." in name else name


def format_doc_result(n: int, doc_type: str, source: str, content: str) -> str:
    """Render one retrieved document (1-based index n) as a tool-result block."""
    header = _SOURCE_HEADER_TEMPLATE.format(n=n, doc_type=doc_type, source=source)
    return f"{header}\n{content}"


def extract_retrieved_sources(messages: list[Any]) -> list[str]:
    """Doc-ID stems retrieved via search_engineering_docs, de-duplicated, in order.

    Walks a LangGraph message list and parses the Source headers out of every
    ToolMessage produced by the docs-search tool. Other tools are ignored.
    """
    stems: list[str] = []
    seen: set[str] = set()
    for msg in messages:
        if getattr(msg, "type", None) != "tool":
            continue
        if getattr(msg, "name", None) != SEARCH_DOCS_TOOL_NAME:
            continue
        content = msg.content if isinstance(msg.content, str) else str(msg.content)
        for path in _SOURCE_HEADER_RE.findall(content):
            stem = source_stem(path)
            if stem and stem not in seen:
                seen.add(stem)
                stems.append(stem)
    return stems
