"""LangSmith evaluators for the Enterprise Architecture Copilot.

Four evaluators run per example:
- keyword_coverage: deterministic, fraction of expected keywords present in the output.
- factuality: LLM-as-judge — does the output agree with reference_facts?
- groundedness: LLM-as-judge — does the output stick to PayLane domain language and concrete facts?
- appropriate_decline: LLM-as-judge — for out-of-scope examples, did the agent decline politely?

LLM-judge evaluators use gpt-4o at temperature=0 with Pydantic structured output, so
results are stable and integers (0.0 / 0.5 / 1.0). For predictable cost, the LLM is
instantiated lazily and reused via `_get_judge()`.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Literal, Optional

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field


# --- Shared judge LLM ---------------------------------------------------------

@lru_cache(maxsize=1)
def _get_judge() -> ChatOpenAI:
    return ChatOpenAI(model="gpt-4o", temperature=0)


# --- Deterministic: keyword_coverage -----------------------------------------

def keyword_coverage(
    inputs: dict, reference_outputs: Optional[dict] = None, outputs: Optional[dict] = None
) -> dict:
    """Fraction of expected keywords (case-insensitive) present in the output.

    Returns 1.0 when no keywords are expected (typical for out-of-scope questions —
    we don't gate on text content, just on the decline judge).
    """
    text = (outputs or {}).get("output", "").lower()
    keywords = (reference_outputs or {}).get("expected_keywords") or []
    if isinstance(keywords, str):
        keywords = [k.strip() for k in keywords.split(",") if k.strip()]
    row: dict = {
        "key": "keyword_coverage",
        "metadata": {"question": (inputs or {}).get("question", "")},
    }
    if not keywords:
        row["score"] = 1.0
        return row
    hits = sum(1 for k in keywords if k.lower() in text)
    row["score"] = hits / len(keywords)
    row["comment"] = f"{hits}/{len(keywords)} keywords matched"
    return row


# --- Pydantic schemas for LLM-as-judge ---------------------------------------

class _Verdict(BaseModel):
    score: Literal[0, 1] = Field(..., description="0 = bad, 1 = good")
    reasoning: str = Field(..., description="One sentence justification")


class _TernaryVerdict(BaseModel):
    score: Literal[0, 1, 2] = Field(..., description="0 = bad, 1 = partial, 2 = good")
    reasoning: str = Field(..., description="One sentence justification")


def _ternary_to_float(score: int) -> float:
    return {0: 0.0, 1: 0.5, 2: 1.0}.get(int(score), 0.0)


# --- Factuality ---------------------------------------------------------------

_FACTUALITY_PROMPT = """You are grading whether an AI assistant's answer agrees with a reference set of facts about a fictional engineering organization.

Reference facts (ground truth):
---
{reference_facts}
---

User question: {question}

Assistant's answer:
---
{answer}
---

Score:
- 2 if the answer is factually consistent with the reference facts (no contradictions, key facts present).
- 1 if the answer is partially consistent (some right, some missing or vague but no clear contradictions).
- 0 if the answer contradicts the reference facts or is largely wrong.

Out-of-scope handling: if the reference facts say the agent should decline AND the assistant's answer is a polite decline (or refusal to speculate), score 2.

Return your verdict via the structured schema."""


def factuality(
    inputs: dict, reference_outputs: Optional[dict] = None, outputs: Optional[dict] = None
) -> dict:
    question = (inputs or {}).get("question", "")
    reference_facts = (reference_outputs or {}).get("reference_facts", "")
    answer = (outputs or {}).get("output", "")

    judge = _get_judge().with_structured_output(_TernaryVerdict)
    verdict: _TernaryVerdict = judge.invoke(
        _FACTUALITY_PROMPT.format(reference_facts=reference_facts, question=question, answer=answer)
    )
    return {
        "key": "factuality",
        "score": _ternary_to_float(verdict.score),
        "comment": verdict.reasoning,
    }


# --- Groundedness -------------------------------------------------------------

_GROUNDEDNESS_PROMPT = """You are grading whether an AI assistant's answer is grounded in concrete PayLane engineering facts versus generic / made-up content.

PayLane is a fictional payments-processing SaaS. Its services include checkout-service, payment-gateway-service, fraud-detection-service, ledger-service, user-profile-service, notification-service, webhook-dispatcher, merchant-onboarding-service, reporting-service, and the deprecated legacy-inventory-service. Teams are Alpha/Beta/Gamma/Sigma/Delta. Document IDs are ADR-NNN, RB-NNN, PM-YYYY-NNN, DD-NNN.

User question: {question}

Assistant's answer:
---
{answer}
---

Score:
- 2 if the answer references specific PayLane entities (service names, team names, document IDs, endpoint paths) AND the claims are concrete (no hand-wavy generalities).
- 1 if the answer is partially grounded (mentions some entities, but is vague or pads with generic content).
- 0 if the answer is generic / hand-wavy / appears to be hallucinated knowledge unrelated to PayLane.

If the question is clearly out-of-scope (weather, recipes, generic programming opinions) and the assistant correctly declines, score 2.

Return your verdict via the structured schema."""


def groundedness(
    inputs: dict, reference_outputs: Optional[dict] = None, outputs: Optional[dict] = None
) -> dict:
    question = (inputs or {}).get("question", "")
    answer = (outputs or {}).get("output", "")

    judge = _get_judge().with_structured_output(_TernaryVerdict)
    verdict: _TernaryVerdict = judge.invoke(
        _GROUNDEDNESS_PROMPT.format(question=question, answer=answer)
    )
    return {
        "key": "groundedness",
        "score": _ternary_to_float(verdict.score),
        "comment": verdict.reasoning,
    }


# --- Appropriate decline ------------------------------------------------------

_DECLINE_PROMPT = """You are grading whether an AI assistant correctly declined an out-of-scope question.

The assistant is supposed to ONLY answer questions about PayLane (a fictional payments SaaS) — its services, runbooks, ADRs, postmortems, and incidents. For any other question (weather, recipes, jokes, generic opinions), it should politely decline and redirect.

User question: {question}

Assistant's answer:
---
{answer}
---

Should the agent have declined? **{should_decline}**

Score:
- 1 if the agent's behavior matches what was expected (declined when it should, answered when it should).
- 0 if the agent did the wrong thing (answered an out-of-scope question, or declined a legitimate PayLane question).

Return your verdict via the structured schema."""


def appropriate_decline(
    inputs: dict, reference_outputs: Optional[dict] = None, outputs: Optional[dict] = None
) -> dict:
    question = (inputs or {}).get("question", "")
    answer = (outputs or {}).get("output", "")
    expected_decline = bool((reference_outputs or {}).get("expected_decline", False))

    judge = _get_judge().with_structured_output(_Verdict)
    verdict: _Verdict = judge.invoke(
        _DECLINE_PROMPT.format(
            question=question, answer=answer, should_decline=str(expected_decline).lower()
        )
    )
    return {
        "key": "appropriate_decline",
        "score": float(verdict.score),
        "comment": verdict.reasoning,
    }


ALL_EVALUATORS = [keyword_coverage, factuality, groundedness, appropriate_decline]
