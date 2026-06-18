---
id: RB-016
title: Production deploy rollback via ArgoCD
status: Accepted
date: 2024-03-15
authors: [team-alpha, team-delta]
services: [checkout-service, merchant-onboarding-service]
---

# Production deploy rollback via ArgoCD

## Symptoms

Unexpected behavior or errors are observed in production shortly after a new deployment. This may include increased error rates in Datadog, failed API calls, or customer complaints.

## Diagnostic Steps

1. **Check Deployment History**: Access ArgoCD to review recent deployment history for the affected service. Identify the last successful deployment prior to the issue.
2. **Review Logs**: Use Loki to review logs from the affected service to identify any anomalies or errors introduced in the latest deployment.
3. **Metrics Analysis**: Analyze Datadog metrics to confirm any spikes in error rates or latency that correlate with the deployment time.
4. **Service Health**: Verify the health of the service using Datadog's APM to ensure that the issue is isolated to the new deployment and not an unrelated infrastructure issue.

## Mitigation

1. **Initiate Rollback**: In ArgoCD, select the application corresponding to the affected service. Click on the "Rollback" option and select the last known good deployment version.
2. **Monitor Rollback Progress**: Track the rollback status in ArgoCD to ensure it completes successfully without errors.
3. **Verify Logs and Metrics**: Once the rollback is complete, use Loki and Datadog to verify that the error rates and service behavior have returned to normal.
4. **Communicate**: Inform stakeholders and affected teams about the rollback and any temporary service disruptions.

## Verification

- Confirm that the service is operating normally post-rollback by checking Datadog metrics for error rates and latency.
- Ensure that logs in Loki do not show any new errors related to the rollback.
- Validate that customer complaints or alerts have ceased.

## Escalation

If the rollback does not resolve the issue within 30 minutes, escalate to the on-call engineer via PagerDuty (`pagerduty-alpha` or `pagerduty-delta`). Provide all diagnostic information and steps taken so far.
