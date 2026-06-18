---
id: ADR-012
title: Sunset legacy-inventory-service
status: Accepted
date: 2024-03-15
authors: [team-gamma]
services: [legacy-inventory-service]
---

# Sunset legacy-inventory-service

## Context

The legacy-inventory-service was part of the original PayLane Commerce platform, which included e-commerce functionalities beyond the current focus on payment processing. Since the pivot to a pure payment-processing SaaS in 2022-Q2, the inventory and catalog functionalities have been deprecated. The service is currently maintained by Team Gamma and is scheduled for sunset by 2025-Q3. This ADR outlines the plan and rationale for deprecating the legacy-inventory-service, ensuring resources are reallocated to core payment processing capabilities.

## Decision

The decision is to sunset the legacy-inventory-service by 2025-Q3. This involves:

- Ceasing all new feature development immediately.
- Maintaining minimal operational support until the sunset date.
- Notifying any remaining users and providing migration assistance to alternative solutions.
- Decommissioning the service infrastructure post-sunset.

## Consequences

**Positive:**

- **Resource Optimization:** Reallocation of engineering resources from maintaining a deprecated service to enhancing core payment processing services.
- **Focus Alignment:** Aligns with PayLane's strategic focus on payment processing, improving service quality and innovation in this domain.
- **Cost Reduction:** Reduces operational overhead associated with maintaining legacy infrastructure.

**Negative:**

- **Customer Impact:** Potential disruption for any remaining users who have not yet migrated.
- **Transition Effort:** Requires coordination and communication efforts to ensure a smooth transition for affected users.

## Alternatives Considered

- **Continue Maintenance:** Rejected due to misalignment with strategic goals and resource inefficiency.
- **Open Source the Service:** Rejected as the service is tightly coupled with deprecated business logic not suitable for open-source community use.
- **Sell the Technology:** Rejected due to limited market interest in a deprecated inventory management solution.
