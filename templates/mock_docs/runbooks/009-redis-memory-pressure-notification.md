---
id: RB-009
title: Redis memory pressure on notification-service
status: Accepted
date: 2024-01-15
authors: [team-beta]
services: [notification-service]
---

# Redis memory pressure on notification-service

## Symptoms

The `notification-service` experiences increased latency and potential timeouts when sending emails or SMS notifications. This is often accompanied by alerts from Datadog indicating high memory usage in Redis, which is used for caching and queuing within the service.

## Diagnostic Steps

1. **Check Datadog Dashboards:**
   - Navigate to the Datadog dashboard for `notification-service`.
   - Look for metrics related to Redis memory usage and cache hit/miss rates.
   - Confirm if memory usage is approaching or exceeding the allocated limit.

2. **Review Logs:**
   - Use Loki to access the logs for `notification-service`.
   - Search for any errors or warnings related to Redis, such as `OOM` (Out of Memory) or connection errors.

3. **Inspect Redis Configuration:**
   - Access the Redis configuration settings.
   - Verify if the `maxmemory` policy is set appropriately (e.g., `volatile-lru` or `allkeys-lru`).
   - Check if any recent changes have been made to the configuration.

4. **Analyze Queue Lengths:**
   - Use Redis CLI to check the length of queues used by `notification-service`.
   - High queue lengths may indicate processing bottlenecks or backlogs.

5. **Evaluate Recent Deployments:**
   - Review recent deployments to `notification-service` for changes that might impact Redis usage, such as increased caching or queue operations.

## Mitigation

1. **Increase Redis Memory Allocation:**
   - If possible, increase the memory allocation for the Redis instance to handle the current load.
   - Ensure this change is within budget and resource constraints.

2. **Optimize Cache Usage:**
   - Identify and remove any unnecessary data being cached.
   - Adjust cache expiration policies to free up memory more aggressively.

3. **Scale Redis Instances:**
   - Consider adding additional Redis instances or enabling Redis clustering to distribute the load.

4. **Throttling and Backoff:**
   - Implement request throttling or exponential backoff in `notification-service` to reduce the load on Redis during peak times.

## Verification

- Monitor the Datadog dashboard for a reduction in Redis memory usage and improved response times for `notification-service`.
- Confirm through logs that there are no recent `OOM` errors or Redis connection issues.
- Verify that notifications are being sent without delays or failures.

## Escalation

- If the issue persists for more than 30 minutes after mitigation steps, escalate to `pagerduty-beta` for immediate assistance from Team Beta.
