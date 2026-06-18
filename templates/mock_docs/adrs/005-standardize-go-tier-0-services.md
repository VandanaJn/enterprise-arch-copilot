---
id: ADR-005
title: Standardize on Go for new tier-0 services
status: Accepted
date: 2022-01-15
authors: [team-alpha, team-sigma]
services: [checkout-service, payment-gateway-service, fraud-detection-service, ledger-service]
related_to: [ADR-003]
---

# Standardize on Go for new tier-0 services

## Context

As PayLane continues to expand its service offerings and scale its operations, the need for a standardized approach to service development has become apparent. Our current architecture includes services written in multiple languages, which introduces complexity in maintenance, onboarding, and scaling efforts. Given the critical nature of our tier-0 services, which include `checkout-service`, `payment-gateway-service`, `fraud-detection-service`, and `ledger-service`, it is essential to adopt a language that offers performance, reliability, and ease of use.

## Decision

We have decided to standardize on Go as the primary programming language for all new tier-0 services. Go's simplicity, strong concurrency model, and efficient performance make it an ideal choice for our high-throughput, low-latency applications. This decision aligns with our existing use of Go for `checkout-service` and `payment-gateway-service`, ensuring consistency and leveraging our team's expertise in the language.

## Consequences

- **Positive:**
  - **Performance:** Go's efficiency and low memory footprint enhance the performance of our critical services.
  - **Consistency:** Standardizing on Go reduces the cognitive load for developers and streamlines the onboarding process.
  - **Community and Support:** Go has a strong community and a wealth of libraries, which accelerates development.

- **Negative:**
  - **Learning Curve:** Team members familiar with other languages may require time to become proficient in Go.
  - **Tooling Transition:** Existing services in other languages may need to be gradually refactored or integrated with Go-based systems, requiring additional effort.

## Alternatives Considered

- **Continue with Multiple Languages:** Rejected due to increased complexity in maintaining diverse codebases and the inefficiencies in scaling.

- **Adopt Python for All Services:** Rejected because Python, while excellent for ML and data services, does not meet the performance requirements for tier-0 services.

- **Use Kotlin for All Services:** Rejected as Kotlin is more suited for JVM-based environments and does not align with our current infrastructure and expertise.
