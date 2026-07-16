"""Pydantic request/response schemas for the API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Body for POST /chat. thread_id continues an existing conversation thread."""

    message: str = Field(..., description="The user's question for the copilot.")
    thread_id: str | None = Field(
        default=None,
        description="Conversation thread to continue; the server mints a UUID when omitted.",
    )


class HealthResponse(BaseModel):
    status: str
    reasons: list[str] = []
