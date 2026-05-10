---
id: PM-2024-007
title: EKS deploy wedged the cluster via misconfigured pod disruption budget
status: Accepted
date: 2024-06-15
authors: [team-alpha, team-delta]
services: [checkout-service, merchant-onboarding-service]
related_to: [PM-2024-001, PM-2024-004]
---

# EKS deploy wedged the cluster via misconfigured pod disruption budget

## Summary

On June 15, 2024, a deployment to our EKS cluster caused a complete service outage due to a misconfigured pod disruption budget (PDB) that led to all pods being evicted simultaneously. This incident impacted multiple services, including `checkout-service` and `merchant-onboarding-service`, and lasted approximately 45 minutes.

## Impact

The incident resulted in a total service outage for critical path services such as `checkout-service`, affecting all customer transactions during the downtime. Approximately 1,200 transactions failed to process, resulting in significant customer frustration and potential revenue loss. The incident lasted from 14:05 to 14:50 UTC, causing a 45-minute downtime.

## Timeline

- **14:00 UTC**: Deployment initiated for `checkout-service` and `merchant-onboarding-service`.
- **14:05 UTC**: PDB misconfiguration causes all pods to be evicted simultaneously.
- **14:10 UTC**: PagerDuty alerts triggered for `pagerduty-alpha` and `pagerduty-delta`.
- **14:20 UTC**: Initial investigation identifies PDB as the root cause.
- **14:30 UTC**: Manual intervention begins to restore pod deployment.
- **14:45 UTC**: Pods begin to recover, services start coming back online.
- **14:50 UTC**: Full service restoration achieved.

## Root Cause

The root cause was a misconfigured PDB that allowed for 100% of pods to be disrupted at once. This configuration error was introduced during a recent update to our deployment scripts and was not caught in code review.

## What Went Well

- Rapid identification of the misconfiguration by the on-call teams, leading to a quick resolution.
- Effective communication between Team Alpha and Team Delta minimized confusion and expedited recovery efforts.

## What Went Wrong

- The PDB misconfiguration was not caught during code review or testing.
- Lack of automated checks for PDB configurations in the CI/CD pipeline.
- Insufficient documentation on the impact of PDB settings led to oversight.

## Action Items

- **Implement automated checks for PDB configurations**: [Team Alpha, Due Q3 2024]
- **Enhance code review process to include configuration validation**: [Team Delta, Due Q3 2024]
- **Update documentation on PDB settings and their impact**: [Team Alpha, Due Q3 2024]
- **Conduct training sessions on Kubernetes best practices**: [Team Delta, Due Q4 2024]
