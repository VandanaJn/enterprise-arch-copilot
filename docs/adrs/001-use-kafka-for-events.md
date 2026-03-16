# ADR 001: Use Kafka for Event Streaming
        
**Status:** Accepted
**Date:** 2023-10-15

## Context
Our monolithic architecture is struggling to handle the volume of checkout processing. We need a robust way to decouple services. RabbitMQ was considered but rejected due to throughput limitations.

## Decision
We will use Apache Kafka as our primary event streaming platform. The `checkout-service` will publish `OrderPlaced` events to the `checkout.events` topic. Downstream services like `inventory-service` and `notification-service` will subscribe to this topic.

## Consequences
- Better isolation between the checkout flow and downstream processing.
- Increased operational complexity (need to manage Kafka clusters).
