---
id: RB-014
title: RDS connection pool exhaustion on user-profile
status: Accepted
date: 2024-03-15
authors: [team-beta]
services: [user-profile-service]
---

# RDS connection pool exhaustion on user-profile

## Symptoms

The `user-profile-service` experiences high latency or timeouts, particularly during peak usage periods. This is often accompanied by errors in the application logs such as `ERROR: remaining connection slots are reserved for non-replication superuser connections`. Datadog may show spikes in database connection errors, and the service may trigger PagerDuty alerts for degraded performance.

## Diagnostic Steps

1. **Check Datadog Metrics:**
   - Navigate to the Datadog dashboard for the `user-profile-service`.
   - Look for spikes in the `db.connection_errors` metric and correlate with the `db.connections` metric to confirm exhaustion.

2. **Review RDS Logs:**
   - Access the RDS console in AWS.
   - Check the `PostgreSQL` logs for connection errors or slow query logs that might indicate resource contention.

3. **Examine Application Logs:**
   - Use Loki to search the `user-profile-service` logs for any errors related to database connectivity.
   - Look for patterns or specific endpoints that might be causing excessive load.

4. **Inspect Connection Pool Settings:**
   - Verify the current connection pool configuration in the `user-profile-service` settings.
   - Ensure that the pool size is appropriately set relative to the RDS instance size and workload.

5. **Evaluate Recent Deployments or Changes:**
   - Review recent changes in the service's GitHub repository that might have affected database usage.
   - Check for recent deployments via ArgoCD that could have introduced issues.

## Mitigation

1. **Increase RDS Instance Size (if necessary):**
   - Evaluate the current RDS instance size and consider upgrading to a larger instance to handle increased connections.

2. **Adjust Connection Pool Size:**
   - Modify the connection pool settings in the `user-profile-service` configuration to better align with the RDS instance's capacity.
   - Deploy the configuration changes using ArgoCD.

3. **Implement Query Optimization:**
   - Identify and optimize slow or inefficient queries that may be holding connections longer than necessary.
   - Consider adding indexes or rewriting queries for better performance.

4. **Introduce Circuit Breakers or Rate Limiting:**
   - Implement circuit breakers to gracefully degrade service under load.
   - Apply rate limiting on endpoints that are heavily used to prevent overwhelming the database.

## Verification

- Monitor the `db.connections` and `db.connection_errors` metrics in Datadog to ensure they return to normal levels.
- Confirm that the application logs no longer show connection-related errors.
- Validate that the service's response times have improved and PagerDuty alerts have ceased.

## Escalation

If the issue persists beyond 30 minutes after implementing the above mitigations, escalate to `pagerduty-beta`. Provide details on all diagnostic steps taken and any changes made to the system.
