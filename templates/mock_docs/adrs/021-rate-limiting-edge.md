---
id: ADR-021
title: Rate limiting at the edge with CloudFront and API Gateway
status: Accepted
date: 2024-03-15
authors: [team-alpha, team-beta]
services: [checkout-service, payment-gateway-service, webhook-dispatcher]
---

# Rate limiting at the edge with CloudFront and API Gateway

## Context

As PayLane scales its payment-processing services, ensuring the stability and reliability of our API endpoints becomes increasingly critical. High traffic spikes, whether due to legitimate usage or malicious activities, can overwhelm our services, leading to degraded performance or outages. Implementing a rate limiting strategy at the edge, using AWS CloudFront and API Gateway, allows us to manage traffic effectively, protect backend services, and maintain service-level objectives (SLOs).

## Decision

We will implement rate limiting at the edge using AWS CloudFront and API Gateway. This approach will protect our tier-0 services, such as `checkout-service` and `payment-gateway-service`, as well as tier-1 services like `webhook-dispatcher`, from excessive traffic. Rate limiting rules will be defined based on IP addresses and API keys, with thresholds set according to each service's capacity and criticality.

- **CloudFront** will handle initial traffic distribution and apply rate limiting rules globally.
- **API Gateway** will enforce additional rate limits, providing a second layer of protection and more granular control.

## Consequences

- **Positive:**
  - **Improved Stability:** Helps prevent service overloads by managing traffic spikes effectively.
  - **Enhanced Security:** Reduces the risk of DDoS attacks by limiting the number of requests from malicious sources.
  - **Cost Efficiency:** Reduces unnecessary load on backend services, potentially lowering operational costs.

- **Negative:**
  - **Complexity:** Increases configuration complexity, requiring careful management of rate limit rules.
  - **Potential for False Positives:** Legitimate users may be rate-limited if thresholds are not carefully calibrated.

## Alternatives Considered

- **Implementing Rate Limiting in Backend Services:** Rejected due to increased latency and reduced effectiveness in early traffic management.
- **Using Third-Party Rate Limiting Solutions:** Rejected due to additional costs and integration complexity.
- **No Rate Limiting:** Rejected as it poses a significant risk to service stability and security.
