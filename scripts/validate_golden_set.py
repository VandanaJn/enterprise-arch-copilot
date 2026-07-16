"""Offline validator for tests/eval/golden_set.json.

Checks structural invariants that would otherwise only surface mid-eval (after
spending API credits): unique IDs, known categories, well-typed fields, and that
every expected_sources entry resolves to a real document in the canonical corpus
(templates/mock_docs/**). Run directly or via tests/eval/test_golden_set_schema.py,
which makes golden-set drift a plain CI failure.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GOLDEN_SET_PATH = REPO_ROOT / "tests" / "eval" / "golden_set.json"
CORPUS_DIR = REPO_ROOT / "templates" / "mock_docs"

KNOWN_CATEGORIES = {
    "factual",
    "single-hop-doc",
    "multi-hop-incident",
    "ambiguous",
    "supersession",
    "negative",
    "out-of-scope",
    "adversarial-scope",
}


def corpus_stems(corpus_dir: Path = CORPUS_DIR) -> set[str]:
    """Filename stems (no directory, no extension) of every corpus markdown doc."""
    return {p.stem for p in corpus_dir.rglob("*.md")}


def validate(rows: list[dict], stems: set[str]) -> list[str]:
    """Return a list of human-readable problems; empty means the set is valid."""
    errors: list[str] = []
    seen_ids: set[str] = set()

    if not isinstance(rows, list) or not rows:
        return ["golden set must be a non-empty JSON array"]

    for i, row in enumerate(rows):
        label = row.get("id", f"row {i}") if isinstance(row, dict) else f"row {i}"
        if not isinstance(row, dict):
            errors.append(f"{label}: not a JSON object")
            continue

        row_id = row.get("id")
        if not isinstance(row_id, str) or not row_id:
            errors.append(f"{label}: missing or non-string id")
        elif row_id in seen_ids:
            errors.append(f"{label}: duplicate id")
        else:
            seen_ids.add(row_id)

        category = row.get("category")
        if category not in KNOWN_CATEGORIES:
            errors.append(f"{label}: unknown category {category!r}")

        question = row.get("question")
        if not isinstance(question, str) or not question.strip():
            errors.append(f"{label}: missing or empty question")

        keywords = row.get("expected_keywords")
        if not isinstance(keywords, list) or any(not isinstance(k, str) for k in keywords):
            errors.append(f"{label}: expected_keywords must be a list of strings")

        if not isinstance(row.get("reference_facts"), str) or not row["reference_facts"].strip():
            errors.append(f"{label}: missing or empty reference_facts")

        if not isinstance(row.get("expected_decline"), bool):
            errors.append(f"{label}: expected_decline must be a boolean")

        if "expected_not_found" in row and not isinstance(row["expected_not_found"], bool):
            errors.append(f"{label}: expected_not_found must be a boolean")

        sources = row.get("expected_sources")
        if sources is not None:
            if not isinstance(sources, list) or any(not isinstance(s, str) for s in sources):
                errors.append(f"{label}: expected_sources must be a list of strings")
            else:
                for stem in sources:
                    if stem not in stems:
                        errors.append(
                            f"{label}: expected_sources stem {stem!r} does not match any "
                            "file under templates/mock_docs/"
                        )

    return errors


def main() -> int:
    rows = json.loads(GOLDEN_SET_PATH.read_text(encoding="utf-8"))
    errors = validate(rows, corpus_stems())
    if errors:
        print(f"golden_set.json: {len(errors)} problem(s):")
        for e in errors:
            print(f"  - {e}")
        return 1

    by_category: dict[str, int] = {}
    for row in rows:
        by_category[row["category"]] = by_category.get(row["category"], 0) + 1
    print(f"golden_set.json: {len(rows)} examples valid.")
    for cat, n in sorted(by_category.items()):
        print(f"  {cat:20s} {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
