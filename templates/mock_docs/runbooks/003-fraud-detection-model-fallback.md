---
id: RB-003
title: Fraud-detection-service model fallback when ML cluster is down
status: Accepted
date: 2023-11-15
authors: [team-sigma]
services: [fraud-detection-service]
---

# Fraud-detection-service model fallback when ML cluster is down

## Symptoms

When the ML cluster supporting the `fraud-detection-service` is down, the service may fail to score transactions, leading to potential delays or failures in payment processing. This can manifest as increased error rates in the `fraud-detection-service` logs, specifically errors related to model unavailability or timeouts.

## Diagnostic Steps

1. **Check Datadog Metrics:**
   - Verify the `fraud-detection-service` dashboard in Datadog for any spikes in error rates or latency metrics.
   - Look for specific error codes indicating model unavailability.

2. **Review Logs in Loki:**
   - Access the `fraud-detection-service` logs in Loki.
   - Search for recent error messages related to model loading or execution failures.

3. **Verify ML Cluster Status:**
   - Confirm the status of the ML cluster by checking the AWS EKS console or using `kubectl` to ensure all pods are running.
   - Identify any issues with pod deployments or resource constraints.

4. **Check Redis Feature Store:**
   - Ensure that Redis, used for the feature store, is operational and not experiencing memory pressure.
   - Use Redis monitoring tools to check for any anomalies.

## Mitigation

1. **Activate Fallback Logic:**
   - If the ML cluster is confirmed down, activate the fallback logic in the `fraud-detection-service` to use cached model results or heuristic-based scoring.
   - This can be done by toggling the feature flag in the service configuration.

2. **Restart ML Cluster Pods:**
   - If the issue is with the ML cluster pods, attempt to restart them using `kubectl` commands.
   - Ensure that there are no underlying resource constraints causing pod failures.

3. **Increase Resource Allocation:**
   - If resource constraints are identified, increase the CPU and memory allocation for the ML cluster pods.
   - Update the EKS deployment configuration and apply the changes.

4. **Notify On-Call Engineer:**
   - If the issue persists, notify the on-call engineer via PagerDuty (`pagerduty-sigma`) for further investigation.

## Verification

- Confirm that the `fraud-detection-service` is processing transactions without errors by monitoring the Datadog metrics for error rate normalization.
- Check that fallback logic is functioning by verifying logs for heuristic-based scoring messages.
- Ensure that the ML cluster is fully operational and all pods are in a running state.

## Escalation

- If the issue is not resolved within 30 minutes, escalate to the on-call engineer from `team-sigma` via PagerDuty (`pagerduty-sigma`).
- If the fallback logic fails to mitigate the issue, escalate to the engineering manager for a potential service degradation announcement.
