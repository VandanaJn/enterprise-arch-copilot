---
id: ADR-025
title: Redis as the primary cache layer
status: Accepted
date: 2023-11-15
authors: [team-alpha, team-sigma]
services: [checkout-service, payment-gateway-service, fraud-detection-service]
related_to: [ADR-006, ADR-007]
---

# Redis as the primary cache layer

## Context

As PayLane continues to scale its payment-processing services, efficient data retrieval and low-latency operations are crucial. Our tier-0 services, such as `checkout-service`, `payment-gateway-service`, and `fraud-detection-service`, require a robust caching solution to handle high transaction volumes and ensure quick response times. Redis, known for its in-memory data store capabilities, provides the speed and reliability needed for these critical services.

## Decision

We will adopt Redis as the primary caching layer for our tier-0 services. This decision aligns with our need for high availability, low-latency access, and simplified data structures. Redis will be used for caching frequently accessed data, reducing load on our primary PostgreSQL databases and improving overall system performance.

## Consequences

**Positive:**
- **Improved Performance:** Redis's in-memory data storage significantly reduces data retrieval times, enhancing user experience during peak loads.
- **Scalability:** Redis supports clustering, allowing us to scale horizontally and manage increased traffic efficiently.
- **Simplicity:** Redis offers simple data structures like strings, hashes, and lists, making it easy to implement and maintain.
- **Integration:** Seamless integration with existing services due to its compatibility with our current tech stack.

**Negative:**
- **Cost:** Running Redis in a high-availability setup incurs additional costs.
- **Complexity:** Requires managing and monitoring an additional infrastructure component.

## Alternatives Considered

- **Memcached:** Rejected due to lack of persistence and advanced data structures.
- **Database Caching:** Using PostgreSQL for caching was dismissed as it would not provide the performance improvements needed.
- **In-App Caching:** Considered but rejected as it would lead to increased complexity in application code and lack of centralized cache management.
