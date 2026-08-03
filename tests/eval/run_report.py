"""Cost / latency / score summary for a LangSmith eval run.

LangSmith already records tokens, cost, and timing on every root run; this module
only surfaces them: it aggregates the rows returned by `langsmith.evaluate()` into
one dict, prints it as a table, and writes a machine-readable JSON artifact
(default: eval_reports/eval_report.json, overridable via EAC_EVAL_REPORT_PATH).
Cross-commit comparison happens by diffing artifacts or in the LangSmith
experiments UI, not a homegrown dashboard.

Note: token/cost totals reflect what the SDK returned at collection time; LangSmith
rolls up usage from child LLM runs asynchronously, so they can read 0 locally right
after a run. The LangSmith experiments UI is authoritative for cost.
"""

from __future__ import annotations

import json
import os
from typing import Any

from src import config


def _percentile(sorted_values: list[float], pct: float) -> float | None:
    if not sorted_values:
        return None
    idx = min(int(round(pct * (len(sorted_values) - 1))), len(sorted_values) - 1)
    return sorted_values[idx]


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _run_latency(run: Any) -> float | None:
    """Seconds the target itself measured, read off the run's outputs.

    `copilot_target` returns `latency_s` alongside its answer, so the number lives
    in the outputs the SDK carries locally rather than in the run timestamps the
    tracing machinery fills in. That is what keeps the percentiles working when
    tracing is disabled. Read defensively: a run may have no outputs at all, and a
    malformed value must not take down the report.
    """
    outputs = getattr(run, "outputs", None)
    if not isinstance(outputs, dict):
        return None
    value = outputs.get("latency_s")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def summarize_results(results: Any) -> dict:
    """Aggregate langsmith.evaluate() result rows into one report dict.

    Reads per-row `run` (tokens/cost/timing), `example` (category metadata), and
    `evaluation_results` (scores). All fields are read defensively so a missing
    attribute degrades to None instead of failing the eval run.
    """
    latencies: list[float] = []
    total_tokens = 0
    total_cost = 0.0
    n_examples = 0
    per_eval: dict[str, list[float]] = {}
    per_category: dict[str, dict[str, list[float]]] = {}

    for row in results:
        n_examples += 1

        run = row.get("run")
        if run is not None:
            total_tokens += int(getattr(run, "total_tokens", 0) or 0)
            total_cost += float(getattr(run, "total_cost", 0) or 0)

        # Prefer the target's own measurement over the run timestamps, which the
        # tracing machinery fills in and which therefore go missing when tracing is
        # off. Fall back to the timestamps so runs whose target does not report a
        # latency still aggregate.
        if run is not None:
            latency = _run_latency(run)
            if latency is None:
                start, end = getattr(run, "start_time", None), getattr(run, "end_time", None)
                if start and end:
                    latency = (end - start).total_seconds()
            if latency is not None:
                latencies.append(latency)

        example = row.get("example")
        metadata = getattr(example, "metadata", None) or {}
        category = metadata.get("category", "unknown")

        ev = row.get("evaluation_results") or {}
        for r in ev.get("results", []):
            if r.score is None:
                continue
            score = float(r.score)
            per_eval.setdefault(r.key, []).append(score)
            per_category.setdefault(category, {}).setdefault(r.key, []).append(score)

    latencies.sort()
    return {
        "experiment": getattr(results, "experiment_name", None),
        "github_sha": os.getenv("GITHUB_SHA"),
        "mode": "quick" if os.getenv("EAC_EVAL_QUICK") == "1" else "full",
        "n_examples": n_examples,
        "total_tokens": total_tokens,
        "total_cost_usd": round(total_cost, 4),
        "latency_p50_s": _percentile(latencies, 0.50),
        "latency_p95_s": _percentile(latencies, 0.95),
        "per_evaluator_means": {k: _mean(v) for k, v in sorted(per_eval.items())},
        "per_category": {
            cat: {k: {"mean": _mean(v), "n": len(v)} for k, v in sorted(evals.items())}
            for cat, evals in sorted(per_category.items())
        },
    }


def format_summary(summary: dict) -> str:
    """Human-readable rendering of a summarize_results() dict."""
    lines = ["=== Evaluation summary ==="]
    lines.append(
        f"experiment={summary.get('experiment')}  mode={summary.get('mode')}  "
        f"examples={summary.get('n_examples')}"
    )
    p50, p95 = summary.get("latency_p50_s"), summary.get("latency_p95_s")
    lines.append(
        f"tokens={summary.get('total_tokens')}  cost_usd={summary.get('total_cost_usd')}  "
        f"latency_p50={p50 if p50 is None else round(p50, 2)}s  "
        f"latency_p95={p95 if p95 is None else round(p95, 2)}s"
    )
    lines.append("-- per evaluator --")
    for key, mean in (summary.get("per_evaluator_means") or {}).items():
        lines.append(f"  {key:24s} mean={'n/a' if mean is None else f'{mean:.2f}'}")
    lines.append("-- per category --")
    for cat, evals in (summary.get("per_category") or {}).items():
        cells = []
        for key, v in evals.items():
            mean = "n/a" if v["mean"] is None else f"{v['mean']:.2f}"
            cells.append(f"{key}={mean}(n={v['n']})")
        lines.append(f"  {cat:20s} " + "  ".join(cells))
    return "\n".join(lines)


def write_report(summary: dict, path: str | None = None) -> str:
    """Write the summary as JSON; returns the path written."""
    path = path or config.eval_report_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)
    return path
