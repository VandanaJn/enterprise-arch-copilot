"""Schema/consistency checks for the golden set — plain unit tests, no API keys.

Runs in normal CI so golden-set drift (typo'd category, dangling expected_sources
after a corpus rename, duplicate id) fails the build instead of surfacing mid-eval.
"""

from __future__ import annotations

import json

from scripts.validate_golden_set import (
    GOLDEN_SET_PATH,
    KNOWN_CATEGORIES,
    corpus_stems,
    validate,
)


def _load_rows() -> list[dict]:
    return json.loads(GOLDEN_SET_PATH.read_text(encoding="utf-8"))


def test_golden_set_is_valid():
    errors = validate(_load_rows(), corpus_stems())
    assert not errors, "golden_set.json invalid:\n" + "\n".join(errors)


def test_golden_set_covers_all_categories():
    categories = {row["category"] for row in _load_rows()}
    assert categories == KNOWN_CATEGORIES


def test_validator_catches_bad_rows():
    stems = {"001-checkout-504-mitigation"}
    rows = [
        {
            "id": "x-01",
            "category": "not-a-category",
            "question": "",
            "expected_keywords": "oops",
            "reference_facts": "",
            "expected_decline": "yes",
            "expected_sources": ["does-not-exist"],
        },
        {
            "id": "x-01",
            "category": "factual",
            "question": "q",
            "expected_keywords": [],
            "reference_facts": "f",
            "expected_decline": False,
        },
    ]
    errors = validate(rows, stems)
    joined = "\n".join(errors)
    for expected in (
        "unknown category",
        "empty question",
        "list of strings",
        "reference_facts",
        "expected_decline",
        "does-not-exist",
        "duplicate id",
    ):
        assert expected in joined
