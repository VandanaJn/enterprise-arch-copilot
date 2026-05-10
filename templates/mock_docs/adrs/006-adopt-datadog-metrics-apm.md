---
id: ADR-006
title: Adopt Datadog as primary metrics and APM platform
status: Accepted
date: 2021-06-15
authors: [team-alpha, team-sigma]
services: [checkout-service, payment-gateway-service, fraud-detection-service]
---

# Adopt Datadog as primary metrics and APM platform

## Context

As PayLane expanded its service-oriented architecture, the need for a comprehensive observability solution became apparent. Our existing monitoring stack, which relied on a combination of open-source tools, was fragmented and lacked the integration necessary for effective incident response and performance optimization. Given the critical nature of our tier-0 services such as `checkout-service`, `payment-gateway-service`, and `fraud-detection-service`, a unified platform for metrics and application performance monitoring (APM) was essential to meet our 99.99% SLO.

## Decision

We decided to adopt Datadog as our primary platform for metrics and APM across all services. Datadog offers a robust, integrated solution that provides real-time visibility into application performance, infrastructure metrics, and logs. This decision aligns with our goals of improving incident response times and gaining deeper insights into service performance.

## Consequences

- **Positive:**
  - **Unified Observability:** Datadog provides a single pane of glass for monitoring metrics, APM, and logs, reducing the cognitive load on engineers and enabling faster incident resolution.
  - **Scalability:** As a SaaS solution, Datadog scales with our infrastructure, supporting our growth without additional operational overhead.
  - **Integration:** Seamless integration with AWS services and our existing toolchain, including PagerDuty for alerting, enhances our incident management capabilities.

- **Negative:**
  - **Cost:** Datadog's pricing model can be expensive as we scale, necessitating careful management of data retention policies and monitored entities.
  - **Vendor Lock-in:** Reliance on a third-party service introduces a dependency that could pose risks if Datadog's service quality changes.

## Alternatives Considered

- **Prometheus and Grafana:** Rejected due to complexity in managing and scaling the infrastructure, which would require significant engineering resources.
- **New Relic:** Considered but ultimately rejected due to less favorable integration capabilities with our existing AWS and Kubernetes stack.
- **Elastic Stack (ELK):** Rejected as it primarily focuses on logs and lacks the comprehensive APM features provided by Datadog.
