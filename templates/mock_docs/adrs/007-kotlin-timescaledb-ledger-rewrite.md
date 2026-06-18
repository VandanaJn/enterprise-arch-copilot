---
id: ADR-007
title: Use Kotlin and TimescaleDB for ledger-service rewrite
status: Accepted
date: 2024-02-15
authors: [team-sigma]
services: [ledger-service]
related_to: [ADR-022]
---

# Use Kotlin and TimescaleDB for ledger-service rewrite

## Context

The existing ledger-service, a critical component of PayLane's payment processing infrastructure, is responsible for maintaining the integrity of financial transactions using a double-entry accounting system. Initially implemented in a different technology stack, the service has exhibited performance and scalability limitations as transaction volumes have grown. These limitations impact our ability to provide real-time financial insights and maintain high availability.

Given the increasing demands on the ledger-service and the need for improved time-series data handling, we have decided to rewrite the service using Kotlin and TimescaleDB. This decision aligns with our strategic goals of leveraging modern, efficient technologies that can handle large-scale data processing and provide robust time-series capabilities.

## Decision

We will rewrite the ledger-service using Kotlin as the primary programming language and TimescaleDB as the database backend. Kotlin offers strong type safety, interoperability with existing Java libraries, and a modern syntax that can enhance developer productivity. TimescaleDB, an extension of PostgreSQL, provides native support for time-series data, which is essential for efficient handling of financial transactions over time.

## Consequences

**Positive:**
- **Improved Performance:** TimescaleDB's time-series capabilities will optimize query performance for financial data analysis.
- **Scalability:** The new architecture will support higher transaction volumes without degradation in performance.
- **Developer Productivity:** Kotlin's modern language features will increase developer efficiency and reduce the likelihood of bugs.
- **Interoperability:** Kotlin's compatibility with Java allows for seamless integration with existing Java-based components.

**Negative:**
- **Migration Complexity:** Transitioning to a new technology stack requires careful planning and execution to avoid data loss or downtime.
- **Learning Curve:** Developers will need to become proficient in Kotlin and TimescaleDB, which may initially slow down development.

## Alternatives Considered

- **Continue with the Existing Stack:** Rejected due to performance and scalability issues that cannot be easily resolved with the current technology.
- **Use Java with TimescaleDB:** Rejected in favor of Kotlin for its modern language features and improved developer experience.
- **Adopt a NoSQL Database:** Rejected due to the need for strong ACID compliance and relational capabilities inherent in financial transactions.
