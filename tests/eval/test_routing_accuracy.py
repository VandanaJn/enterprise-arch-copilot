"""Unit tests for the routing_accuracy evaluator: no API keys, normal CI.

routing_accuracy grades the triage LLM's route choice directly against the route
each example's category implies (via CATEGORY_TO_MODE). These are plain,
deterministic tests that call the evaluator with hand-built inputs.
"""

from __future__ import annotations

from scripts.validate_golden_set import KNOWN_CATEGORIES
from tests.eval.evaluators import CATEGORY_TO_MODE, routing_accuracy


def _route(category: str | None, mode: str | None) -> dict:
    return routing_accuracy(
        inputs={},
        reference_outputs={"category": category},
        outputs={"mode": mode},
    )


def test_routing_accuracy_match_scores_one():
    row = _route("multi-hop-incident", "incident")
    assert row["score"] == 1.0


def test_routing_accuracy_mismatch_scores_zero():
    row = _route("multi-hop-incident", "general")
    assert row["score"] == 0.0


def test_routing_accuracy_ambiguous_is_skipped():
    row = _route("ambiguous", "general")
    assert row["score"] is None


def test_routing_accuracy_missing_mode_is_skipped():
    row = _route("factual", "")
    assert row["score"] is None


def test_routing_accuracy_unknown_category_is_skipped():
    row = _route("not-a-category", "general")
    assert row["score"] is None


def test_category_to_mode_covers_every_known_category():
    # Guards against golden-set drift: a new category must get an explicit route
    # (or an explicit None) here, not silently fall through to "skipped".
    assert set(CATEGORY_TO_MODE) == KNOWN_CATEGORIES
