---
id: ADR-001
title: Adopt RabbitMQ for inter-service messaging
status: Accepted
date: 2021-01-15
authors: [team-alpha]
services: [checkout-service, user-profile-service]
superseded_by: ADR-002
---

# Adopt RabbitMQ for inter-service messaging

## Context

In early 2021, PayLane was transitioning from a monolithic architecture to a microservices-based system. The need for a reliable, scalable inter-service messaging solution was critical to ensure seamless communication between newly extracted services such as `checkout-service` and `user-profile-service`. At this time, RabbitMQ was a popular choice for message brokering, known for its robust features and ease of integration with existing systems.

## Decision

PayLane decided to adopt RabbitMQ as the inter-service messaging platform. This decision was driven by RabbitMQ's proven track record in the industry, its support for various messaging patterns (e.g., publish/subscribe, request/reply), and its ability to handle high-throughput scenarios. RabbitMQ's compatibility with Go and Python, the languages used for our services, was also a significant factor.

## Consequences

**Positive:**
- **Scalability:** RabbitMQ provided the necessary scalability to support the growing number of microservices.
- **Reliability:** Its robust message delivery guarantees ensured that messages were not lost, contributing to system reliability.
- **Ease of use:** RabbitMQ's comprehensive documentation and community support facilitated quick adoption and integration.

**Negative:**
- **Operational Overhead:** Managing RabbitMQ clusters required additional operational resources and expertise.
- **Latency:** In some cases, RabbitMQ introduced additional latency compared to direct service-to-service communication.

## Alternatives Considered

- **Kafka:** Rejected initially due to its complexity and the team's lack of experience with it at the time.
- **ActiveMQ:** Dismissed due to lower community support and fewer integrations compared to RabbitMQ.
- **ZeroMQ:** Not chosen because it is more of a socket library than a full-fledged message broker, lacking some of the features needed for our use case.

This decision was later superseded by ADR-007, which adopted Kafka for event streaming as the organization matured and our requirements evolved.
