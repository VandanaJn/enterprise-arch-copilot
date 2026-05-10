---
id: DD-002
title: Observability v2: adopt OpenTelemetry across all services
status: Proposed
date: 2024-01-15
authors: [team-alpha, team-sigma, team-beta, team-delta]
services: [checkout-service, payment-gateway-service, fraud-detection-service, ledger-service, user-profile-service, notification-service, webhook-dispatcher, merchant-onboarding-service, reporting-service]
---

# Observability v2: adopt OpenTelemetry across all services

## Goal

The primary goal of this design is to enhance the observability of PayLane's services by adopting OpenTelemetry (OTel) as the standard for distributed tracing and metrics collection. This will improve our ability to monitor, debug, and optimize the performance of our services across the board.

## Non-Goals

- This design does not aim to replace existing logging solutions such as Loki.
- It does not cover changes to the CI/CD pipeline or deployment strategies.
- It does not include changes to the existing alerting mechanisms on PagerDuty.

## Proposal

The proposal is to implement OpenTelemetry across all active services at PayLane. OpenTelemetry will be used for collecting and exporting telemetry data, including traces and metrics, to Datadog, our existing observability platform.

### Architecture Overview

1. **Instrumentation**: Each service will be instrumented using OpenTelemetry SDKs appropriate for its language. For instance, Go services like `checkout-service` and `payment-gateway-service` will use the Go SDK, while Python services like `fraud-detection-service` will use the Python SDK.

2. **Data Collection**: OpenTelemetry will collect traces and metrics from each service. These will include request latencies, error rates, and resource utilization metrics.

3. **Exporting**: The collected data will be exported to Datadog using the OpenTelemetry Collector. The Collector will be deployed as a sidecar in our EKS clusters to aggregate and forward telemetry data.

4. **Visualization and Alerts**: Datadog will be configured to visualize the telemetry data and integrate it with existing alerting mechanisms to notify on-call teams via PagerDuty.

## API / Schema Changes

No changes to public APIs or schemas are required. However, internal telemetry data schemas will be standardized according to OpenTelemetry specifications.

## Migration Plan

1. **Phase 1: Pilot**
   - Select a non-critical service, such as `reporting-service`, to pilot OpenTelemetry integration.
   - Validate data collection and export to Datadog.

2. **Phase 2: Incremental Rollout**
   - Gradually instrument and deploy OpenTelemetry across tier-1 services, starting with `user-profile-service` and `notification-service`.
   - Monitor for any performance impacts.

3. **Phase 3: Full Deployment**
   - Complete instrumentation of tier-0 services, including `checkout-service` and `payment-gateway-service`.
   - Conduct thorough testing to ensure no degradation in service performance.

4. **Phase 4: Optimization and Training**
   - Optimize telemetry data collection to reduce overhead.
   - Conduct training sessions for engineering teams on using OpenTelemetry and Datadog effectively.

## Risks

- **Performance Overhead**: Instrumentation may introduce latency. Mitigation involves careful monitoring and optimization.
- **Data Volume**: Increased telemetry data could lead to higher costs and storage requirements in Datadog.

## Open Questions

- How will we handle backward compatibility with existing monitoring tools during the transition?
- What specific metrics and traces should be prioritized for collection across different services?
