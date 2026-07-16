"""Pure helpers and types for the incident-first supervisor graph (unit-testable, no I/O)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from langchain_core.messages import AIMessage, AnyMessage, BaseMessage
from pydantic import BaseModel, Field


class TriageResult(BaseModel):
    """Structured output from the triage LLM step."""

    mode: Literal["incident", "general", "out_of_scope"] = Field(
        ...,
        description='Use "incident" for outages, errors, HTTP codes, latency, '
        "endpoint/path failures, or who-to-page. Use general for ADRs, design rationale, "
        'or catalog-only lookups. Use "out_of_scope" for questions unrelated to PayLane '
        "(weather, jokes, recipes, generic programming help, world knowledge).",
    )
    endpoint_hint: str | None = Field(
        default=None,
        description="API path or URL fragment if mentioned, else null.",
    )
    service_hint: str | None = Field(
        default=None,
        description="Service name if mentioned, else null.",
    )
    symptoms_summary: str | None = Field(
        default=None,
        description="Short restatement of symptoms or empty.",
    )


def route_target_for_mode(
    mode: str | None,
) -> Literal["structured_agent", "general_agent", "decline_node"]:
    """Graph conditional edge: where to go after triage."""
    if mode == "incident":
        return "structured_agent"
    if mode == "out_of_scope":
        return "decline_node"
    return "general_agent"


def latest_user_text(messages: Sequence[BaseMessage]) -> str:
    for m in reversed(messages):
        if m.type == "human":
            return m.content if isinstance(m.content, str) else str(m.content)
    return ""


def extract_final_assistant_text(messages: Sequence[AnyMessage]) -> str:
    """Last non-tool-calling AI message content (typical final answer in a ReAct trace)."""
    for m in reversed(messages):
        if not isinstance(m, AIMessage):
            continue
        if m.tool_calls:
            continue
        if m.content:
            return m.content if isinstance(m.content, str) else str(m.content)
    return ""
