---
id: ADR-009
title: Adopt schema registry for Kafka topics
status: Accepted
date: 2023-06-15
authors: [team-alpha, team-sigma]
services: [checkout-service, payment-gateway-service, fraud-detection-service]
related_to: [ADR-007]
---

# Adopt schema registry for Kafka topics

## Context

Since adopting Kafka as our primary event streaming platform (see ADR-007), we have encountered challenges related to schema evolution and compatibility across services. Inconsistent schemas have led to deserialization errors and increased the complexity of maintaining event consumers. A schema registry can help manage and enforce schema compatibility, ensuring that producers and consumers adhere to a consistent contract.

## Decision

We will adopt a schema registry for managing Kafka topic schemas. This registry will provide a centralized repository for schema definitions and enforce compatibility checks. We will use Confluent Schema Registry, which integrates seamlessly with our existing Kafka infrastructure.

## Consequences

- **Positive:**
  - **Improved Compatibility:** Ensures backward and forward compatibility of schemas, reducing runtime errors.
  - **Centralized Management:** Provides a single source of truth for schema definitions, simplifying updates and governance.
  - **Developer Efficiency:** Reduces the cognitive load on developers by automating schema validation and compatibility checks.

- **Negative:**
  - **Operational Overhead:** Introduces additional infrastructure to maintain, requiring monitoring and potential scaling.
  - **Learning Curve:** Developers need to familiarize themselves with the schema registry and its integration with Kafka.

## Alternatives Considered

- **Manual Schema Management:** Rejected due to high risk of human error and lack of automated compatibility checks.
- **Avro without Registry:** Rejected as it does not provide centralized schema management or compatibility enforcement.
- **JSON Schemas:** Rejected due to lack of native support for compatibility checks and higher payload size.
