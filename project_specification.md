# The Enterprise Integration & Architecture Copilot

**Target Audience:** Staff / Lead Software Engineers
**Focus:** Large-scale distributed systems, APIs, Cloud Infrastructure (AWS), and Event-Driven Architectures.

## Overview
A Hybrid RAG system acting as an intelligent technical advisor. It combines structured platform definitions with unstructured engineering context to assist in designing, building, and operating mission-critical distributed systems. 

This directly addresses the core responsibilities seen in Staff SE roles (e.g., AppFolio, FINRA, Ridgeline, PayPal, Affirm) which require deep expertise in microservices, cloud-native deployments, API design, and system reliability.

## Data Sources

### 1. Structured Data (The "What" and "Where")
*   **API & Event Schemas:** OpenAPI/Swagger specs (REST), AsyncAPI specs (Kafka topics, SNS/SQS messaging payloads, Protobufs).
*   **Cloud Infrastructure:** Terraform state files (`.tfstate`) or AWS CDK configurations mapping out EKS clusters, load balancers, API Gateways (Kong), and serverless functions (Lambda).
*   **Data Models:** SQL (PostgreSQL, Aurora) and NoSQL (DynamoDB, MongoDB) table schemas and indexes.
*   **Observability:** Structured metrics and active alerts from Datadog/Prometheus (e.g., latency SLOs, error rates, capacity).

### 2. Unstructured Data (The "Why" and "How")
*   **Design Documentation:** Architecture Decision Records (ADRs), Request for Comments (RFCs), and system design proposals.
*   **Operational Knowledge:** Incident post-mortems, operational runbooks, and internal engineering wikis.
*   **Collaboration History:** Jira tickets, GitHub Pull Request descriptions/comments, and engineering Slack threads.
*   **External References:** Vendor documentation (AWS best practices, Kafka deployment guides).

## Key Capabilities & Use Cases

1.  **Impact Analysis for Event-Driven Systems:**
    *   *Query:* "If we modify the JSON structure of the `PaymentProcessed` event payload, which microservices and downstream data pipelines will break, and did we document a fallback strategy in the initial ADR?"
    *   *Action:* The RAG queries the Graph/Relational DB for the dependency map (Structured) and retrieves the original Architecture Decision Record (Unstructured) to explain the design rationale to the developer.

2.  **Infrastructure as Code (IaC) Validation & Generation:**
    *   *Query:* "Give me the Terraform configuration to deploy a high-availability ElastiCache Redis cluster that complies with our secure coding practices for PII highlighted in last week's security review."
    *   *Action:* The system retrieves the internal security wiki policies (Unstructured) and the existing `.tf` module parameters (Structured) to generate compliant, secure Terraform code.

3.  **API Integration & Microservice Scaffolding:**
    *   *Query:* "Create a production-ready FastAPI microservice skeleton that interacts with the user profile gRPC service and adheres to our standard rate-limiting and Datadog monitoring patterns."
    *   *Action:* It pulls up the company's OpenAPI standards (Structured) and implementation guides (Unstructured) to generate a robust code foundation.

4.  **Incident Response & Triage Copilot:**
    *   *Query:* "We're seeing a spike in `504 Gateway Timeout` errors on the Kong API Gateway for the finance engine route. Find the last post-mortem with this issue and list the rollback steps."
    *   *Action:* Retrieves the structured Datadog alert context and searches the vector database for similar historical post-mortems and corresponding runbooks to guide the on-call engineer.
