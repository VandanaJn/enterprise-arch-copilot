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

# A cited doc-id stem in answer text, e.g. [001-checkout-504-mitigation]. Requires at
# least one hyphen (stems always have one) and rejects markdown links [text](url).
_CITATION_RE = re.compile(r"\[([0-9a-z]+(?:-[0-9a-z]+)+)\](?!\()")


def source_stem(path: str) -> str:
    """Filename without directory or extension, tolerant of / and \\ separators.

    Stems (not full paths) are the stable document identifier: the same doc lives
    under docs/... in dev and tests/test_data/docs/... in the test sandbox.
    """
    name = path.replace("\\", "/").rsplit("/", 1)[-1]
    return name.rsplit(".", 1)[0] if "." in name else name


def format_doc_result(
    n: int, doc_type: str, source: str, content: str, note: str | None = None
) -> str:
    """Render one retrieved document (1-based index n) as a tool-result block.

    The `Cite as: [stem]` line gives the LLM the exact token to cite, so citations
    match the stems the retrieval evaluators check. `note` is an optional extra
    header line (e.g. an ADR's supersession status); it sits below `Cite as:` so
    the header format the extractor parses is unchanged.
    """
    header = _SOURCE_HEADER_TEMPLATE.format(n=n, doc_type=doc_type, source=source)
    lines = [header, f"Cite as: [{source_stem(source)}]"]
    if note:
        lines.append(note)
    lines.append(content)
    return "\n".join(lines)


def split_doc_blocks(tool_output: str) -> list[str]:
    """Split one `search_engineering_docs` result into its per-document blocks.

    Lives here, next to `format_doc_result`, so the split and the format cannot
    drift apart. Text with no document header (an error string, or "No relevant
    documentation found.") yields no blocks.
    """
    starts = [m.start() for m in _SOURCE_HEADER_RE.finditer(tool_output or "")]
    if not starts:
        return []
    bounds = starts + [len(tool_output)]
    return [tool_output[a:b].strip() for a, b in zip(bounds, bounds[1:], strict=False)]


def doc_block_source(block: str) -> str:
    """Source stem of one document block, or "" if it has no header."""
    match = _SOURCE_HEADER_RE.search(block or "")
    return source_stem(match.group(1)) if match else ""


def renumber_doc_block(block: str, n: int) -> str:
    """Rewrite a block's `Document N` index, for merging results from several queries."""
    return re.sub(r"^--- Document \d+ ", f"--- Document {n} ", block, count=1)


def extract_cited_sources(answer_text: str) -> list[str]:
    """Doc-ID stems the answer cites inline (e.g. [001-checkout-504-mitigation]).

    De-duplicated, in order of first appearance.
    """
    stems: list[str] = []
    seen: set[str] = set()
    for stem in _CITATION_RE.findall(answer_text or ""):
        low = stem.lower()
        if low not in seen:
            seen.add(low)
            stems.append(low)
    return stems


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
