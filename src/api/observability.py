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

from prometheus_client import Counter
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
