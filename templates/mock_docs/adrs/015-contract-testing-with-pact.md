---
id: ADR-015
title: Contract testing with Pact between services
status: Accepted
date: 2024-01-15
authors: [team-alpha, team-beta]
services: [checkout-service, user-profile-service, notification-service]
related_to: [ADR-003, ADR-013]
---

# Contract testing with Pact between services

## Context

As PayLane continues to evolve its microservices architecture, ensuring seamless integration between services is critical. The existing integration testing strategy has limitations, particularly in terms of identifying contract mismatches between services early in the development cycle. This has occasionally led to runtime failures and increased debugging time. To address these challenges, we propose adopting contract testing using Pact, which allows us to define and verify service interactions more effectively.

## Decision

PayLane will adopt Pact for contract testing between services. Pact will be used to define consumer-driven contracts, which will be verified against provider services. This approach will help ensure that services adhere to agreed-upon API contracts, reducing the likelihood of integration issues.

- **Implementation**: Each service team will be responsible for writing and maintaining Pact contracts for their services. These contracts will be stored in a central repository and verified as part of the CI/CD pipeline.
- **Scope**: Initially, we will focus on tier-0 services such as `checkout-service` and `payment-gateway-service`, and gradually expand to other services.

## Consequences

- **Positive**:
  - Improved reliability of service integrations by detecting contract mismatches early.
  - Reduced time spent on debugging integration issues, leading to faster development cycles.
  - Enhanced collaboration between teams through clear contract definitions.

- **Negative**:
  - Initial setup and learning curve for teams unfamiliar with contract testing.
  - Additional maintenance overhead for keeping contracts up-to-date with service changes.

## Alternatives Considered

- **End-to-end testing**: Rejected due to high maintenance cost and slower feedback loop.
- **Manual contract verification**: Rejected as it is error-prone and not scalable.
- **Relying solely on integration tests**: Rejected because it does not provide early feedback on contract changes.
