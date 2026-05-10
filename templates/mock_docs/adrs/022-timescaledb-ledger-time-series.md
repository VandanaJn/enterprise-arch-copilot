---
id: ADR-022
title: TimescaleDB choice for ledger time-series data
status: Accepted
date: 2024-03-15
authors: [team-sigma]
services: [ledger-service]
related_to: [ADR-012, ADR-005]
---

# TimescaleDB choice for ledger time-series data

## Context

As PayLane continues to grow, the need for a robust and efficient time-series database to handle the increasing volume of ledger transactions becomes crucial. The ledger-service, responsible for maintaining double-entry accounting records, requires a database that can efficiently manage time-series data while providing high availability and scalability. Previously, PostgreSQL was used, but it has shown limitations in handling the specific needs of time-series data, such as efficient querying of time-based data and storage optimization.

## Decision

We have decided to adopt TimescaleDB as the primary database for the ledger-service. TimescaleDB, an extension of PostgreSQL, is optimized for time-series data, offering features such as automatic partitioning, compression, and native support for time-series queries. This decision aligns with our existing use of PostgreSQL, minimizing the learning curve for our engineering teams and leveraging existing operational expertise.

## Consequences

- **Positive:**
  - **Improved Query Performance:** TimescaleDB's optimizations for time-series data significantly enhance query performance, especially for time-based queries.
  - **Scalability:** Automatic partitioning allows for seamless scaling as data volume grows, ensuring consistent performance.
  - **Storage Efficiency:** Native compression features reduce storage requirements, lowering operational costs.
  - **Compatibility:** As an extension of PostgreSQL, TimescaleDB maintains compatibility with existing tools and workflows.

- **Negative:**
  - **Complexity in Transition:** Migrating existing data from PostgreSQL to TimescaleDB requires careful planning and execution to avoid downtime.
  - **Operational Overhead:** Initial setup and configuration of TimescaleDB introduce additional operational overhead.

## Alternatives Considered

- **Continue with PostgreSQL:** Rejected due to its limitations in handling time-series data efficiently.
- **Use a NoSQL Time-Series Database:** Rejected as it would require significant changes to our existing architecture and workflows, increasing complexity and risk.
- **Adopt InfluxDB:** Rejected due to concerns about integration complexity and lack of native support for relational data, which is crucial for our ledger-service.
