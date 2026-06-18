---
id: ADR-014
title: Use Loki for centralized logs
status: Accepted
date: 2023-05-15
authors: [team-alpha, team-beta]
services: [checkout-service, user-profile-service]
related_to: [ADR-006]
---

# Use Loki for centralized logs

## Context

As PayLane continues to scale its operations and expand its service offerings, the need for a robust and centralized logging solution becomes increasingly critical. Currently, logging is handled in an ad-hoc manner, with logs scattered across various systems, making it difficult to perform efficient debugging, monitoring, and auditing. This lack of centralized logging can lead to increased time in diagnosing issues and potential gaps in compliance with PCI-DSS and SOC 2 requirements.

## Decision

We will adopt Loki as our centralized logging solution. Loki is chosen for its seamless integration with our existing observability stack, specifically with Grafana, which is already used for visualizing metrics from Datadog. Loki's design as a horizontally scalable, highly available log aggregation system aligns with our needs for reliability and scalability.

## Consequences

- **Positive:**
  - **Improved Debugging:** Centralized logs will enable faster root cause analysis by providing a single source of truth for all service logs.
  - **Scalability:** Loki's architecture supports horizontal scaling, which will accommodate PayLane's growing data volume.
  - **Cost Efficiency:** Loki is designed to be cost-effective, especially when compared to traditional logging solutions, as it does not index the content of logs.
  - **Seamless Integration:** Loki integrates well with Grafana, enhancing our existing monitoring dashboards without additional overhead.

- **Negative:**
  - **Initial Setup Complexity:** The initial setup and configuration of Loki may require significant effort and coordination across teams.
  - **Learning Curve:** Teams will need to familiarize themselves with Loki's query language and operational nuances.

## Alternatives Considered

- **Elasticsearch:** Rejected due to higher operational complexity and cost.
- **Splunk:** Rejected because of its high licensing costs, which are not justified given our current budget constraints.
- **Fluentd with S3:** Rejected as it lacks the real-time querying capabilities that Loki provides.
