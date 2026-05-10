---
id: ADR-019
title: API versioning strategy with path-based v1, v2
status: Accepted
date: 2024-01-15
authors: [team-alpha, team-beta]
services: [checkout-service, payment-gateway-service, user-profile-service]
---

# API versioning strategy with path-based v1, v2

## Context

As PayLane continues to evolve its services, maintaining backward compatibility while allowing for new features and improvements is crucial. Our current API endpoints are versioned implicitly, leading to potential conflicts and confusion during updates. To address this, we propose a path-based versioning strategy for our APIs, ensuring clear version delineation and smoother transitions for our merchants.

## Decision

We will adopt a path-based versioning strategy for all public APIs. Each version of an API will be explicitly defined in the URL path (e.g., `/api/v1/checkout`), allowing clients to specify which version they are using. This approach will be applied across all customer-facing services, including `checkout-service`, `payment-gateway-service`, and `user-profile-service`.

## Consequences

**Positive:**
- **Clear Versioning:** Clients can easily identify which version of the API they are interacting with, reducing ambiguity during updates.
- **Backward Compatibility:** Older versions can be maintained alongside newer ones, allowing clients time to migrate at their own pace.
- **Simplified Deprecation:** Deprecated versions can be phased out in a structured manner, with clear communication to clients.

**Negative:**
- **Increased Maintenance:** Multiple versions of the API will need to be maintained, potentially increasing the complexity of support and development.
- **Documentation Overhead:** Each version will require separate documentation, increasing the effort needed to keep documentation up to date.

## Alternatives Considered

- **Header-based Versioning:** Rejected due to potential complexity for clients in managing headers and the risk of misconfiguration leading to unexpected behavior.
- **No Versioning:** Rejected as it would lead to breaking changes for clients with every update, causing significant disruption and dissatisfaction.
- **Query Parameter Versioning:** Rejected as it can be less intuitive for clients and complicates URL structures, making it harder to manage and document effectively.
