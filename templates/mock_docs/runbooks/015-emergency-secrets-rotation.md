---
id: RB-015
title: Emergency secrets rotation after suspected leak
status: Accepted
date: 2024-01-15
authors: [team-alpha, team-beta]
services: [checkout-service, payment-gateway-service, user-profile-service]
---

# Emergency secrets rotation after suspected leak

## Symptoms

A suspected leak of sensitive secrets such as API keys or database credentials can lead to unauthorized access and potential data breaches. Symptoms include unexpected changes in system behavior, unauthorized access logs, or alerts from security monitoring tools indicating anomalies.

## Diagnostic Steps

1. **Verify Alerts:** Check Datadog and Sentry for any alerts or error messages related to unauthorized access or anomalies in the `checkout-service`, `payment-gateway-service`, and `user-profile-service`.
2. **Audit Logs:** Review AWS CloudTrail logs for any suspicious activity, such as unauthorized API calls or changes to IAM roles and policies.
3. **Access Patterns:** Analyze access logs in PostgreSQL and Redis to identify any unusual access patterns or failed login attempts.
4. **Service Health:** Confirm the operational status of all services involved by checking their health endpoints and ensuring they are functioning as expected.

## Mitigation

1. **Rotate Secrets:**
   - Use AWS Secrets Manager to rotate all affected secrets immediately.
   - Update the secrets in the respective service configurations (e.g., environment variables for `checkout-service`, `payment-gateway-service`, `user-profile-service`).
2. **Deploy Updates:**
   - Use ArgoCD to deploy the updated configurations across all environments, ensuring that all services are using the new secrets.
3. **Revoke Access:**
   - Revoke any potentially compromised IAM roles or API keys and issue new ones.
4. **Notify Stakeholders:**
   - Inform all relevant stakeholders, including security and compliance teams, about the incident and actions taken.

## Verification

- Confirm that all services are operational and using the new secrets by checking their logs and health endpoints.
- Verify that unauthorized access attempts have ceased by monitoring logs and alerts.
- Ensure that all stakeholders have acknowledged the incident resolution and are satisfied with the actions taken.

## Escalation

If the issue persists beyond 30 minutes after rotation, or if there are signs of ongoing unauthorized access, escalate to the on-call engineers for `pagerduty-alpha` and `pagerduty-beta`. Additionally, notify the security team for further investigation and potential incident response.
