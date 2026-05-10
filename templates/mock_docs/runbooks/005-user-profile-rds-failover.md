---
id: RB-005
title: User-profile-service RDS failover to read-replica
status: Accepted
date: 2024-03-15
authors: [team-beta]
services: [user-profile-service]
---

# User-profile-service RDS failover to read-replica

## Symptoms

The `user-profile-service` experiences increased latency or downtime due to issues with the primary RDS instance. This can manifest as HTTP 500 errors on API endpoints like `GET /api/v1/users/profile` and `POST /api/v1/users`. Datadog alerts for high latency or error rates may trigger, and Sentry may log increased exceptions related to database connectivity.

## Diagnostic Steps

1. **Check Datadog Dashboards:**
   - Verify the latency and error rate metrics for `user-profile-service`.
   - Confirm if there are any alerts related to RDS instance health.

2. **Inspect RDS Console:**
   - Log into the AWS RDS console.
   - Check the status of the primary instance and any ongoing maintenance events or failover triggers.

3. **Review Application Logs:**
   - Use Loki to review logs from `user-profile-service` for any database connection errors.

4. **Check Replica Lag:**
   - In the AWS RDS console, check the replication lag of the read-replica to ensure it is minimal.

## Mitigation

1. **Initiate Manual Failover:**
   - In the AWS RDS console, select the primary instance.
   - Choose the option to promote the read-replica to a standalone instance if the primary is unrecoverable.

2. **Update Application Configuration:**
   - Modify the `user-profile-service` configuration to point to the new primary instance.
   - Update the connection string in the Secrets Manager if necessary.

3. **Deploy Configuration Changes:**
   - Use ArgoCD to deploy the updated configuration to the EKS cluster.

4. **Monitor Transition:**
   - Continuously monitor Datadog for any anomalies in the service performance post-failover.

## Verification

- Confirm that the `user-profile-service` endpoints are responding with expected latency and without errors.
- Verify that Datadog metrics for latency and error rates have returned to normal levels.
- Ensure that no new database connection errors appear in the logs.

## Escalation

- If the issue persists for more than 30 minutes after mitigation steps, escalate to `pagerduty-beta` for further investigation and support.
