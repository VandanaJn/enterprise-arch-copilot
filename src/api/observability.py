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

from prometheus_client import REGISTRY, Counter
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
        "guardrail_blocks": guardrail_blocks,
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
