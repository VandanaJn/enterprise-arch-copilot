---
id: PM-2024-002
title: Payment-gateway-service Stripe credential rotation incident
status: Accepted
date: 2024-03-15
authors: [team-alpha]
services: [payment-gateway-service]
related_to: [PM-2024-001]
---

# Payment-gateway-service Stripe credential rotation incident

## Summary

On March 15, 2024, a credential rotation for the `payment-gateway-service`'s integration with Stripe led to failed payment authorizations for approximately 45 minutes. The issue was caused by an outdated secret in AWS Secrets Manager that was not updated during the rotation process.

## Impact

Customers experienced payment authorization failures, resulting in approximately 1,200 failed transactions during the incident. The incident lasted for 45 minutes, affecting merchants' ability to process payments and potentially leading to lost sales and customer dissatisfaction. The severity was classified as high due to the impact on the critical payment path.

## Timeline

- **2024-03-15 10:00 UTC**: Credential rotation initiated as part of routine security maintenance.
- **2024-03-15 10:05 UTC**: First alerts triggered in Datadog indicating an increase in authorization errors (HTTP 401).
- **2024-03-15 10:10 UTC**: Team Alpha on-call engineer notified via PagerDuty.
- **2024-03-15 10:15 UTC**: Investigation commenced; initial hypothesis pointed to a network issue.
- **2024-03-15 10:25 UTC**: Root cause identified as outdated Stripe credentials in AWS Secrets Manager.
- **2024-03-15 10:30 UTC**: Credentials updated in AWS Secrets Manager.
- **2024-03-15 10:35 UTC**: Services restarted to pick up new credentials.
- **2024-03-15 10:45 UTC**: Incident resolved; normal operations resumed.

## Root Cause

The root cause was an oversight in the credential rotation process, where the updated Stripe API keys were not correctly propagated to AWS Secrets Manager. As a result, the `payment-gateway-service` continued to use expired credentials, leading to authorization failures.

## What Went Well

- Rapid identification of the issue once the correct hypothesis was formed.
- Efficient communication and coordination among Team Alpha members during the incident.
- Quick resolution once the root cause was identified, minimizing downtime.

## What Went Wrong

- The credential rotation checklist did not include a verification step to ensure updated credentials were correctly stored in AWS Secrets Manager.
- Initial misdiagnosis of the issue as a network problem delayed resolution.

## Action Items

- **Update Credential Rotation Procedure**: Enhance the existing rotation checklist to include verification of credential updates in AWS Secrets Manager. **Owner: Team Alpha**. **Due: 2024-Q2**.
- **Monitoring Enhancements**: Implement additional monitoring to alert on credential expiry and misconfigurations. **Owner: Team Alpha**. **Due: 2024-Q3**.
- **Incident Response Training**: Conduct a training session focused on credential-related incidents to improve initial diagnosis accuracy. **Owner: Team Alpha**. **Due: 2024-Q3**.
