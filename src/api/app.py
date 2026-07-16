"""FastAPI application factory for the Enterprise Architecture Copilot.

Run locally with `make serve` (uvicorn src.api.app:app). The graph is compiled once
at startup into app.state; the existing lazy singletons in src.agent materialize on
first use and are released on shutdown via close_connections().
"""

from __future__ import annotations

import logging
import os
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from src import config
from src.agent import close_connections, create_enterprise_copilot, detect_prompt_injection
from src.api.observability import (
    RequestContextMiddleware,
    configure_json_logging,
    record_guardrail_outcome,
    setup_metrics,
)
from src.api.rate_limit import SlidingWindowLimiter
from src.api.schemas import ChatRequest
from src.api.sse import chat_event_stream

logger = logging.getLogger(__name__)


def _health_reasons() -> list[str]:
    reasons = []
    if not os.path.isfile(config.db_file()):
        reasons.append(f"SQLite DB not found: {config.db_file()}")
    if not os.path.isdir(config.chroma_dir()):
        reasons.append(f"Chroma dir not found: {config.chroma_dir()}")
    return reasons


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        configure_json_logging()
        app.state.agent = create_enterprise_copilot()
        if config.warm_injection_detector():
            # Load the DeBERTa classifier now so the first request doesn't pay
            # model-load latency. detect_prompt_injection fails open on errors.
            detect_prompt_injection("startup warm-up ping")
        logger.info("copilot agent ready")
        yield
        close_connections()

    app = FastAPI(
        title="Enterprise Architecture Copilot API",
        description="SSE chat API over the LangGraph incident copilot.",
        lifespan=lifespan,
    )
    app.add_middleware(RequestContextMiddleware)
    setup_metrics(app)
    limiter = SlidingWindowLimiter()

    @app.get("/healthz")
    async def healthz():
        reasons = _health_reasons()
        if reasons:
            return JSONResponse(
                status_code=503, content={"status": "unhealthy", "reasons": reasons}
            )
        return {"status": "ok", "reasons": []}

    @app.post("/chat")
    async def chat(request: Request, body: ChatRequest):
        client_ip = request.client.host if request.client else "unknown"
        if not limiter.allow(client_ip, config.rate_limit_per_minute()):
            raise HTTPException(
                status_code=429, detail="Rate limit exceeded; try again in a minute."
            )

        thread_id = body.thread_id or str(uuid.uuid4())
        run_id = uuid.uuid4()
        run_config = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": config.recursion_limit(),
            "run_id": run_id,
        }
        stream = chat_event_stream(
            request.app.state.agent,
            body.message,
            thread_id,
            run_config,
            on_complete=record_guardrail_outcome,
            run_id=str(run_id) if config.debug_mode() else None,
        )
        return EventSourceResponse(stream)

    @app.get("/", include_in_schema=False)
    async def root():
        # Placeholder until the chat UI ships (Phase C); keeps / reserved.
        return {
            "service": "enterprise-arch-copilot",
            "chat": "POST /chat (SSE)",
            "health": "GET /healthz",
            "metrics": "GET /metrics",
        }

    return app


app = create_app()
