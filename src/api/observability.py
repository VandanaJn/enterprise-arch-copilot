"""Service-layer observability: structured JSON logs, metrics, guardrail counters.

Boundary (see DECISIONS.md §6): LangSmith owns LLM/agent traces via env-var
auto-instrumentation; this module owns the HTTP service side. No OTel collectors,
no Grafana, no Sentry: for a single-container demo they are weight without signal.
"""

from __future__ import annotations

import json
import logging
import time
import uuid

from prometheus_client import REGISTRY, Counter, Histogram
from prometheus_fastapi_instrumentator import Instrumentator
from starlette.middleware.base import BaseHTTPMiddleware

from src.agent import _READONLY_SQL_ERROR, DECLINE_MESSAGE, PROMPT_INJECTION_MESSAGE

# One counter, labeled by which guardrail fired. Pairs with the red-team suite:
# the same layers that are threshold-tested offline are counted in production.
GUARDRAIL_BLOCKS = Counter(
    "eac_guardrail_blocks_total",
    "Requests blocked or declined by a guardrail layer",
    labelnames=("guardrail",),
)

# Per-node wall-clock, so a slow turn can be attributed to a step rather than to
# "the agent". The incident path is a serial chain (triage -> structured_agent ->
# runbook_agent -> synthesize) and each hop is at least one LLM round trip; without
# this, /metrics/summary only shows the total. Measured at the stream boundary
# (see chat_event_stream), which keeps src/agent.py free of metrics imports.
# Buckets span a sub-second guardrail node to a multi-call ReAct sub-agent.
NODE_DURATION = Histogram(
    "eac_node_duration_seconds",
    "Wall-clock duration of one graph node",
    labelnames=("node",),
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 4, 8, 15, 30, 60),
)

# Time to first token is the latency the user actually feels. On the incident path
# only `synthesize` streams, so this is close to the total; on the general path the
# ReAct agent streams much earlier. The gap between the two is the signal.
TIME_TO_FIRST_TOKEN = Histogram(
    "eac_time_to_first_token_seconds",
    "Seconds from the start of a chat turn to the first answer token streamed",
    buckets=(0.25, 0.5, 1, 2, 4, 8, 15, 30, 60),
)


def record_node_duration(node: str, seconds: float) -> None:
    """Observe one completed graph node. Called from the stream's on_node_complete hook."""
    NODE_DURATION.labels(node=node).observe(seconds)


def record_time_to_first_token(seconds: float) -> None:
    """Observe the first user-facing token of a turn. At most once per turn."""
    TIME_TO_FIRST_TOKEN.observe(seconds)


class JsonLogFormatter(logging.Formatter):
    """One JSON object per log line; extra fields ride along when present."""

    _EXTRA_FIELDS = ("request_id", "thread_id", "path", "method", "status", "duration_ms")

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in self._EXTRA_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                entry[field] = value
        if record.exc_info:
            entry["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


def configure_json_logging(level: int = logging.INFO) -> None:
    """Route root logging through the JSON formatter (idempotent)."""
    root = logging.getLogger()
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    root.handlers = [handler]
    root.setLevel(level)


_access_logger = logging.getLogger("eac.api.access")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assign a request id, time the request, emit one JSON access-log line."""

    async def dispatch(self, request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 1)
        response.headers["X-Request-ID"] = request_id
        _access_logger.info(
            "request handled",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response


def setup_metrics(app) -> None:
    """Expose /metrics with default HTTP series (latency histogram, counts, errors)."""
    Instrumentator(excluded_handlers=["/metrics"]).instrument(app).expose(
        app, endpoint="/metrics", include_in_schema=False
    )


def _histogram_quantile(buckets: list[tuple[float, float]], q: float) -> float | None:
    """Interpolated quantile from Prometheus cumulative buckets (same math as PromQL).

    `buckets` is `(le, cumulative_count)` pairs including the `+Inf` bucket. Returns
    None when there are no observations. Beyond the last finite bucket the estimate
    is clamped to that bucket's upper bound (we can't interpolate into `+Inf`).
    """
    buckets = sorted(buckets, key=lambda b: b[0])
    if not buckets:
        return None
    total = buckets[-1][1]  # the +Inf bucket holds the full count
    if total <= 0:
        return None
    rank = q * total
    prev_le, prev_count = 0.0, 0.0
    for le, cum in buckets:
        if cum >= rank:
            if le == float("inf"):
                return prev_le
            span = cum - prev_count
            if span <= 0:
                return le
            return prev_le + (le - prev_le) * ((rank - prev_count) / span)
        prev_le, prev_count = le, cum
    return buckets[-1][0]


def _collect_samples() -> dict[str, list[tuple[dict, float]]]:
    """Snapshot the default registry as {sample_name: [(labels, value), ...]}."""
    out: dict[str, list[tuple[dict, float]]] = {}
    for family in REGISTRY.collect():
        for sample in family.samples:
            out.setdefault(sample.name, []).append((sample.labels, sample.value))
    return out


def metrics_summary() -> dict:
    """Human-readable digest of the Prometheus series exposed at /metrics.

    Folds the raw exposition text into request counts by endpoint, `/chat` average
    latency, overall latency percentiles, and guardrail-block tallies, so a
    developer can read a pulse without a Prometheus scraper.
    """
    samples = _collect_samples()

    by_endpoint = []
    total_requests = 0
    for labels, value in samples.get("http_requests_total", []):
        count = int(value)
        total_requests += count
        by_endpoint.append(
            {
                "handler": labels.get("handler", ""),
                "method": labels.get("method", ""),
                "status": labels.get("status", ""),
                "count": count,
            }
        )
    by_endpoint.sort(key=lambda r: (-r["count"], r["handler"], r["method"], r["status"]))

    # /chat average from the per-handler histogram's count + sum.
    chat_count = _handler_value(samples, "http_request_duration_seconds_count", "/chat")
    chat_sum = _handler_value(samples, "http_request_duration_seconds_sum", "/chat")
    chat_latency = None
    if chat_count:
        chat_latency = {"count": int(chat_count), "avg_seconds": round(chat_sum / chat_count, 2)}

    # Overall percentiles from the high-resolution (many-bucket) histogram.
    highr = []
    for labels, value in samples.get("http_request_duration_highr_seconds_bucket", []):
        le = labels.get("le", "")
        highr.append((float("inf") if le == "+Inf" else float(le), value))
    overall_latency = None
    if highr:
        overall_latency = {
            "count": int(max(v for _, v in highr)),
            "p50_seconds": _round3(_histogram_quantile(highr, 0.50)),
            "p95_seconds": _round3(_histogram_quantile(highr, 0.95)),
            "p99_seconds": _round3(_histogram_quantile(highr, 0.99)),
        }

    guardrail_blocks = {
        labels.get("guardrail", ""): int(value)
        for labels, value in samples.get("eac_guardrail_blocks_total", [])
    }

    return {
        "requests": {"total": total_requests, "by_endpoint": by_endpoint},
        "chat_latency": chat_latency,
        "overall_latency": overall_latency,
        "node_latency": _node_latency(samples),
        "time_to_first_token": _percentile_summary(samples, "eac_time_to_first_token_seconds"),
        "guardrail_blocks": guardrail_blocks,
    }


def _node_latency(samples: dict) -> list[dict]:
    """Per-node timings, slowest average first, so the top row names the bottleneck.

    `total_seconds` is carried alongside the average because they answer different
    questions: the average finds the slow step, the total finds the step worth
    optimizing when one node is called far more often than another.
    """
    counts = {
        labels.get("node", ""): value
        for labels, value in samples.get("eac_node_duration_seconds_count", [])
    }
    sums = {
        labels.get("node", ""): value
        for labels, value in samples.get("eac_node_duration_seconds_sum", [])
    }
    rows = [
        {
            "node": node,
            "count": int(count),
            "avg_seconds": round(sums.get(node, 0.0) / count, 3),
            "total_seconds": round(sums.get(node, 0.0), 3),
        }
        for node, count in counts.items()
        if count
    ]
    rows.sort(key=lambda r: (-r["avg_seconds"], r["node"]))
    return rows


def _percentile_summary(samples: dict, metric: str) -> dict | None:
    """count / avg / p50 / p95 for an unlabeled histogram, or None if never observed."""
    buckets = []
    for labels, value in samples.get(f"{metric}_bucket", []):
        le = labels.get("le", "")
        buckets.append((float("inf") if le == "+Inf" else float(le), value))
    count = next(iter(samples.get(f"{metric}_count", [])), (None, 0.0))[1]
    total = next(iter(samples.get(f"{metric}_sum", [])), (None, 0.0))[1]
    if not count:
        return None
    return {
        "count": int(count),
        "avg_seconds": round(total / count, 3),
        "p50_seconds": _round3(_histogram_quantile(buckets, 0.50)),
        "p95_seconds": _round3(_histogram_quantile(buckets, 0.95)),
    }


def _handler_value(samples: dict, name: str, handler: str) -> float | None:
    """First sample value for `name` whose handler label matches, or None."""
    for labels, value in samples.get(name, []):
        if labels.get("handler") == handler:
            return value
    return None


def _round3(x: float | None) -> float | None:
    return round(x, 3) if x is not None else None


def record_guardrail_outcome(final_mode: str, messages: list) -> None:
    """Classify a finished chat turn and bump the matching guardrail counter.

    Called from the stream's on_complete hook. Rejections carry a fixed message
    from the guardrail node; read-only SQL blocks surface as tool errors.
    """
    for msg in messages:
        if getattr(msg, "type", "") == "tool":
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            if _READONLY_SQL_ERROR in content:
                GUARDRAIL_BLOCKS.labels(guardrail="readonly-sql").inc()

    final_texts = [
        (m.content if isinstance(m.content, str) else str(m.content))
        for m in messages
        if getattr(m, "type", "") == "ai"
    ]
    last_text = final_texts[-1] if final_texts else ""

    if final_mode == "rejected":
        if PROMPT_INJECTION_MESSAGE in last_text:
            GUARDRAIL_BLOCKS.labels(guardrail="prompt-injection").inc()
        else:
            GUARDRAIL_BLOCKS.labels(guardrail="input-validation").inc()
    elif final_mode == "out_of_scope" or DECLINE_MESSAGE in last_text:
        GUARDRAIL_BLOCKS.labels(guardrail="out-of-scope").inc()
