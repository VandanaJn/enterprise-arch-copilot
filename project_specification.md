# The Enterprise Integration & Architecture Copilot

**Target Audience:** Staff / Lead Software Engineers
**Focus:** Large-scale distributed systems, APIs, and operational knowledge.

## Overview

A hybrid RAG system that acts as an intelligent technical advisor. It combines structured metadata (service catalog, API endpoints) with unstructured engineering documentation (ADRs, runbooks) so engineers can ask questions and get answers that draw from both sources.

**Incident-first workflow:** The runtime is a **supervisor LangGraph**. A lightweight **triage** step classifies each turn as **incident** (outages, error codes, endpoint failures, who-to-page) or **general** (ADRs, design rationale, simple catalog lookups). Incident turns run a **multi-step chain**: SQL-only agent (catalog / endpoints) → vector-only agent (runbooks) → **synthesis** into a structured **incident brief**. General turns use a single ReAct-style agent with all tools, matching the original routing behavior.

## Data Sources

### 1. Structured Data (SQLite)
*   **Service Catalog:** A table listing microservices with name, owner team, version, on-call rotation, and repository URL.
*   **API Endpoints:** A table mapping API path and HTTP method to the owning service (foreign key to service catalog).

### 2. Unstructured Data (Vector Store)
*   **Architecture Decision Records (ADRs):** Markdown files describing *why* architectural choices were made (e.g., why Kafka was chosen, why checkout was migrated to AWS).
*   **Operational Runbooks:** Markdown files describing *how* to handle specific incidents (e.g., 504 mitigation for checkout, user-profile DB failover).

Documents are chunked semantically, embedded, and stored in a local ChromaDB with metadata (e.g. `document_type`: adr or runbook) for hybrid filtering.

## Key Capabilities & Use Cases

1.  **Pure unstructured (vector) search**
    *   *Query:* "What was the rationale behind migrating our payment gateway to the new AWS architecture?"
    *   *Action:* Triage routes to the **general** agent; it uses the vector tool, retrieves relevant ADR chunks, and summarizes the "why".

2.  **Pure structured (SQL) search**
    *   *Query:* "Who is the owner of the user-profile-service and what is the current deployed version?"
    *   *Action:* Triage routes to the **general** agent; it queries SQLite and returns team and version.

3.  **Hybrid / incident search**
    *   *Query:* "The /api/v1/checkout endpoint is failing with a 504 timeout. Who do I contact, and what is the runbook to mitigate this?"
    *   *Action:* Triage routes to **incident** flow: SQL tools resolve service and ownership, vector tools retrieve runbook chunks, then synthesis produces an **incident brief** (summary, ownership/paging, mitigation steps, evidence, gaps).

### Incident brief (incident path)

Final replies follow a consistent template: **Summary**, **Ownership / paging**, **Runbook / mitigation steps**, **Evidence**, **Gaps**—grounded only in tool output; missing data is called out explicitly.

## Future data sources (backlog)

Optional ingestion ideas for a later phase (not required for the current mock corpus):

* Postmortems or incident timelines (new doc type + metadata).
* SLO / error-budget tables or links to dashboards (structured or semi-structured).
* Escalation policies or PagerDuty integration IDs (structured).
* OpenAPI / protobuf snippets per service (structured or vector with `document_type`).

## Implementation note

Graph and tools live in `src/agent.py`; triage schema and pure routing helpers live in `src/incident_workflow.py` for unit testing without LLM calls.
