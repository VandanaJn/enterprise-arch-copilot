---
id: ADR-002
title: Adopt Kafka for event streaming
status: Accepted
date: 2022-08-12
authors: [team-alpha, team-sigma]
services: [checkout-service, payment-gateway-service]
supersedes: [ADR-001]
---

# Adopt Kafka for event streaming

## Context

In 2022-Q3, PayLane decided to transition from RabbitMQ to Apache Kafka for inter-service messaging. This decision was driven by the need for a more robust and scalable event streaming platform to support our growing transaction volume and the increasing complexity of our service architecture. RabbitMQ, while effective for initial service decomposition, presented limitations in terms of message throughput and persistence, which became apparent as our customer base and transaction volume grew.

## Decision

We have decided to adopt Apache Kafka as our primary event streaming platform. Kafka's distributed architecture and high throughput capabilities make it well-suited for our needs, particularly in handling the critical path of transaction processing in services like `checkout-service` and `payment-gateway-service`.

## Consequences

**Positive:**
- **Scalability:** Kafka's ability to handle a large number of events and high throughput aligns with our growth trajectory.
- **Durability:** Kafka's persistent log storage ensures reliable message delivery, reducing data loss risks.
- **Ecosystem:** Kafka's rich ecosystem of tools and integrations supports advanced analytics and monitoring.

**Negative:**
- **Complexity:** The operational complexity of managing a Kafka cluster is higher than RabbitMQ.
- **Learning Curve:** Teams need to upskill to effectively use Kafka and its associated tools.

## Alternatives Considered

- **Continue with RabbitMQ:** Rejected due to scalability and persistence limitations.
- **Amazon SQS:** Rejected as it lacks the streaming capabilities required for our use case.
- **Apache Pulsar:** Considered but rejected due to less mature ecosystem compared to Kafka.
