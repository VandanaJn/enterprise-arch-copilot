---
id: ADR-020
title: Error budget policy and on-call escalation
status: Accepted
date: 2024-05-15
authors: [team-alpha, team-sigma]
services: [checkout-service, payment-gateway-service, fraud-detection-service, ledger-service]
---

# Error budget policy and on-call escalation

## Context

As PayLane continues to grow, maintaining high service reliability is crucial for our tier-0 services, which include `checkout-service`, `payment-gateway-service`, `fraud-detection-service`, and `ledger-service`. These services are on the critical path for our payment processing and directly impact revenue. To ensure reliability, we need a structured approach to managing service performance and incidents. Implementing an error budget policy allows us to balance innovation and reliability by quantifying acceptable failure rates. Additionally, a clear on-call escalation process will ensure timely incident response and resolution.

## Decision

We will adopt an error budget policy that allocates a specific amount of allowable downtime or failure for each service, based on their Service Level Objectives (SLOs). This policy will be integrated into our on-call escalation procedures to ensure that incidents are addressed promptly and effectively.

- **Error Budget Policy:**
  - Define error budgets based on SLOs: 99.99% for tier-0 services.
  - Track error budget consumption using Datadog and PagerDuty.
  - If a service exceeds its error budget, freeze feature releases until the service is back within acceptable limits.

- **On-Call Escalation Process:**
  - Define clear escalation paths for each team (`pagerduty-alpha`, `pagerduty-sigma`).
  - Implement a tiered response system: initial response, escalation to team lead, and further escalation to engineering management if unresolved.
  - Use PagerDuty to automate escalations based on incident severity and duration.

## Consequences

- **Positive:**
  - Improved service reliability by aligning development priorities with operational performance.
  - Faster incident resolution through a structured escalation process.
  - Better visibility into service health and performance trends.

- **Negative:**
  - Potential delays in feature releases if error budgets are exceeded.
  - Increased operational overhead to monitor and manage error budgets and escalations.

## Alternatives Considered

- **No formal error budget policy:** Rejected due to lack of structured reliability management.
- **Manual escalation process:** Rejected due to inefficiency and potential for human error in incident response.
