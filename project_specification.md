# The Enterprise Integration & Architecture Copilot

**Target Audience:** Staff / Lead Software Engineers
**Focus:** Large-scale distributed systems, APIs, and operational knowledge.

## Overview

A hybrid RAG system that acts as an intelligent technical advisor. It combines structured metadata (service catalog, API endpoints) with unstructured engineering documentation (ADRs, runbooks) so engineers can ask questions and get answers that draw from both sources.

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
    *   *Action:* The agent routes to the vector DB tool, retrieves relevant ADR chunks, and summarizes the "why".

2.  **Pure structured (SQL) search**
    *   *Query:* "Who is the owner of the user-profile-service and what is the current deployed version?"
    *   *Action:* The agent routes to the SQL tool, runs a SELECT against the service catalog, and returns team and version.

3.  **Hybrid search**
    *   *Query:* "The /api/v1/checkout endpoint is failing with a 504 timeout. Who do I contact, and what is the runbook to mitigate this?"
    *   *Action:* The agent queries SQL to find which service owns the endpoint and who owns it, then queries the vector DB for runbooks for that service, and returns a consolidated answer with contact and steps.

The agent is a single LangGraph router with three tools: search over engineering docs (vector), query the SQL database, and list all services (for discovery). It chooses which tool(s) to use based on the user question.
