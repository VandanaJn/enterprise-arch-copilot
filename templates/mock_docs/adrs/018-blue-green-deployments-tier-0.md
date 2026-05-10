---
id: ADR-018
title: Blue/green deployments for tier-0 services
status: Accepted
date: 2024-03-15
authors: [team-alpha, team-sigma]
services: [checkout-service, payment-gateway-service, fraud-detection-service, ledger-service]
related_to: [ADR-011, ADR-005]
---

# Blue/green deployments for tier-0 services

## Context

As PayLane continues to scale its operations, ensuring high availability and minimizing downtime during deployments for tier-0 services is crucial. These services, including `checkout-service`, `payment-gateway-service`, `fraud-detection-service`, and `ledger-service`, are critical to our payment processing pipeline. Current deployment strategies involve rolling updates, which, while effective, can still lead to brief periods of instability or degraded performance. To enhance our deployment strategy, we propose adopting blue/green deployments for these tier-0 services.

## Decision

We will implement blue/green deployments for all tier-0 services. This approach involves maintaining two identical environments, "blue" and "green." During a deployment, the new version of the service is deployed to the inactive environment (e.g., "green"), and once validated, traffic is switched from the active environment (e.g., "blue") to the inactive one. This strategy allows for quick rollback in case of issues and ensures zero-downtime deployments.

## Consequences

- **Positive:**
  - **Zero-downtime deployments:** Users experience no downtime during updates, maintaining service availability.
  - **Fast rollback capability:** If a deployment fails, traffic can be quickly switched back to the stable environment.
  - **Improved testing:** New deployments can be fully tested in the "green" environment before going live.
  - **Reduced risk of deployment errors:** By isolating new changes in a separate environment, we minimize the risk of impacting live traffic.

- **Negative:**
  - **Increased infrastructure cost:** Maintaining two identical environments doubles infrastructure requirements.
  - **Complexity in environment management:** Managing two environments requires careful orchestration and monitoring.

## Alternatives Considered

- **Rolling updates:** Retained for non-tier-0 services due to lower risk and complexity.
- **Canary releases:** Rejected due to potential for partial exposure of issues to users, which is unacceptable for tier-0 services.
- **Dark launches:** Not suitable as they do not provide the same level of assurance for zero-downtime as blue/green deployments.
