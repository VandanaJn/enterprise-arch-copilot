---
id: ADR-010
title: Webhook retry semantics with exponential backoff
status: Accepted
date: 2024-05-15
authors: [team-beta]
services: [webhook-dispatcher]
related_to: [ADR-009]
---

# Webhook retry semantics with exponential backoff

## Context

The `webhook-dispatcher` service is responsible for delivering webhooks to external merchant systems. Currently, the service retries failed webhook deliveries using a fixed delay strategy. This approach has led to issues with rate limiting and unnecessary load on both our infrastructure and merchant systems, especially during peak failure periods. To improve reliability and reduce unnecessary load, we need a more sophisticated retry mechanism.

## Decision

We will implement exponential backoff with jitter for webhook retry semantics. This approach will involve increasing the delay between retries exponentially, with a random jitter added to prevent thundering herd problems. The retry mechanism will be configurable, allowing us to adjust parameters such as the initial delay, maximum delay, and maximum number of retries.

## Consequences

- **Positive:**
  - Reduces the risk of overwhelming merchant systems with repeated webhook attempts.
  - Decreases load on our infrastructure during failure scenarios, improving overall system stability.
  - Provides flexibility to adjust retry parameters based on merchant feedback and system performance.

- **Negative:**
  - Complexity increases in the `webhook-dispatcher` codebase due to the introduction of new retry logic.
  - Potential for longer delays in successful webhook delivery if initial failures occur, impacting time-sensitive notifications.

## Alternatives Considered

- **Fixed Delay Retry:** Rejected due to existing issues with rate limiting and load.
- **Linear Backoff:** Rejected as it does not sufficiently spread out retry attempts, leading to similar issues as fixed delay.
- **No Retry:** Rejected because it would significantly reduce the reliability of webhook deliveries.
