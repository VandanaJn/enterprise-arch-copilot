"""Unit tests for tests/eval/run_report.py using synthetic LangSmith result rows."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from types import SimpleNamespace

from tests.eval.run_report import format_summary, summarize_results, write_report


def _row(category: str, scores: dict[str, float | None], seconds: float, tokens: int, cost: float):
    start = datetime(2026, 1, 1, 12, 0, 0)
    return {
        "run": SimpleNamespace(
            start_time=start,
            end_time=start + timedelta(seconds=seconds),
            total_tokens=tokens,
            total_cost=cost,
        ),
        "example": SimpleNamespace(metadata={"category": category}),
        "evaluation_results": {
            "results": [SimpleNamespace(key=k, score=v) for k, v in scores.items()]
        },
    }


def _synthetic_results():
    return [
        _row("factual", {"keyword_coverage": 1.0, "retrieval_recall": None}, 2.0, 100, 0.001),
        _row("factual", {"keyword_coverage": 0.5, "retrieval_recall": None}, 4.0, 200, 0.002),
        _row("single-hop-doc", {"keyword_coverage": 1.0, "retrieval_recall": 1.0}, 6.0, 300, 0.003),
        _row("out-of-scope", {"appropriate_decline": 1.0}, 1.0, 50, 0.0005),
    ]


def test_summarize_results_aggregates_scores_and_costs():
    summary = summarize_results(_synthetic_results())

    assert summary["n_examples"] == 4
    assert summary["total_tokens"] == 650
    assert summary["total_cost_usd"] == 0.0065
    # Nearest-rank percentiles over sorted [1.0, 2.0, 4.0, 6.0]
    assert summary["latency_p50_s"] == 4.0
    assert summary["latency_p95_s"] == 6.0

    means = summary["per_evaluator_means"]
    assert means["keyword_coverage"] == (1.0 + 0.5 + 1.0) / 3
    assert means["retrieval_recall"] == 1.0  # None scores are skipped
    assert means["appropriate_decline"] == 1.0

    per_cat = summary["per_category"]
    assert per_cat["factual"]["keyword_coverage"] == {"mean": 0.75, "n": 2}
    assert per_cat["out-of-scope"]["appropriate_decline"] == {"mean": 1.0, "n": 1}
    # retrieval_recall was None for factual rows, so it never appears there.
    assert "retrieval_recall" not in per_cat["factual"]


def test_summarize_results_tolerates_missing_fields():
    rows = [{"run": None, "example": None, "evaluation_results": None}]
    summary = summarize_results(rows)
    assert summary["n_examples"] == 1
    assert summary["total_tokens"] == 0
    assert summary["latency_p50_s"] is None
    assert summary["per_evaluator_means"] == {}


def test_format_summary_renders_all_sections():
    text = format_summary(summarize_results(_synthetic_results()))
    for expected in ("Evaluation summary", "per evaluator", "per category", "keyword_coverage"):
        assert expected in text


def test_write_report_creates_json(tmp_path):
    summary = summarize_results(_synthetic_results())
    path = write_report(summary, str(tmp_path / "reports" / "eval_report.json"))
    on_disk = json.loads(open(path, encoding="utf-8").read())
    assert on_disk["n_examples"] == 4
    assert on_disk["total_tokens"] == 650
