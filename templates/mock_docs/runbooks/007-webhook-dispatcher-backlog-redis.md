---
id: RB-007
title: Webhook-dispatcher backlog overflowing Redis
status: Accepted
date: 2024-06-15
authors: [team-beta]
services: [webhook-dispatcher]
---

# Webhook-dispatcher backlog overflowing Redis

## Symptoms

The `webhook-dispatcher` service experiences a backlog, causing Redis to overflow. This results in delayed or failed webhook deliveries, impacting merchant notifications and potentially causing customer dissatisfaction.

## Diagnostic Steps

1. **Check Redis Metrics:**
   - Use Datadog to monitor Redis memory usage and keyspace metrics. Look for signs of memory exhaustion or a rapid increase in the number of keys.
   
2. **Inspect Webhook Queue Length:**
   - Use the Redis CLI to check the length of the webhook queue. A significantly large queue length indicates a processing bottleneck.
   
3. **Review Service Logs:**
   - Access logs from the `webhook-dispatcher` via Loki. Look for error messages or warnings that indicate processing delays or failures.
   
4. **Analyze Kafka Lag:**
   - Check the Kafka consumer lag for the `webhook-dispatcher` topic. High lag may suggest that the service is unable to process messages as fast as they are being produced.

5. **Evaluate System Load:**
   - Use Datadog to assess CPU and memory utilization of the `webhook-dispatcher` pods in EKS. High utilization may contribute to processing delays.

## Mitigation

1. **Increase Redis Memory Allocation:**
   - Temporarily increase the memory allocation for Redis in AWS to handle the current backlog.

2. **Scale Webhook-Dispatcher Pods:**
   - Use ArgoCD to scale up the number of `webhook-dispatcher` pods in EKS to improve processing throughput.

3. **Throttle Incoming Webhooks:**
   - Implement rate limiting on incoming webhook requests to reduce the load on the `webhook-dispatcher`.

4. **Clear Stale Entries:**
   - Manually clear stale or failed webhook entries from Redis to free up memory and reduce backlog.

## Verification

- **Redis Memory Stabilization:**
  - Confirm via Datadog that Redis memory usage has stabilized and is within acceptable limits.

- **Queue Length Reduction:**
  - Verify that the length of the webhook queue in Redis is decreasing and approaching normal levels.

- **Log Monitoring:**
  - Ensure that error rates in the `webhook-dispatcher` logs have decreased and that normal processing has resumed.

## Escalation

- If the backlog persists for more than 30 minutes despite mitigation efforts, escalate to `pagerduty-beta` for further investigation and assistance.
