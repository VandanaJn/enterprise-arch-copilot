---
id: RB-010
title: Merchant-onboarding-service stuck applications in KYC review
status: Accepted
date: 2024-03-15
authors: [team-delta]
services: [merchant-onboarding-service]
---

# Merchant-onboarding-service stuck applications in KYC review

## Symptoms

Merchants report that their onboarding process is stuck at the KYC review stage. This results in new merchants being unable to complete the onboarding process, potentially leading to lost business opportunities.

## Diagnostic Steps

1. **Check MongoDB for Stuck Documents**: Query the `merchant-onboarding-service` MongoDB database to identify any documents where the KYC status is neither 'approved' nor 'rejected'. Use the following query:
   ```json
   db.merchantApplications.find({ "kycStatus": { "$nin": ["approved", "rejected"] } })
   ```

2. **Review Logs for Errors**: Access the logs via Loki to check for any errors or exceptions related to KYC processing. Look for error codes or stack traces that might indicate a failure in the KYC processing logic.

3. **Check Kafka Topic for Backlog**: Verify the `merchant-onboarding.events` Kafka topic for any backlog that might indicate a delay in processing KYC events. Use the Kafka monitoring tools to assess consumer lag.

4. **Inspect External KYC Provider Status**: Confirm the operational status of any external KYC verification services. Check for any outages or degraded performance that could impact the processing of KYC applications.

## Mitigation

1. **Restart Stuck Processes**: If documents are stuck, manually trigger a re-evaluation of the KYC status by updating the status field to 'pending' and allowing the system to reprocess them.

2. **Clear Kafka Backlog**: If there is a significant backlog in the Kafka topic, increase the number of consumer instances temporarily to process the backlog faster.

3. **Resolve External Dependencies**: If the issue is with an external KYC provider, contact their support to resolve any ongoing issues. Consider switching to a backup provider if the issue persists.

4. **Fix Application Logic**: If a bug in the application logic is identified, deploy a hotfix to resolve the issue. Ensure that the fix is thoroughly tested before deployment.

## Verification

- Confirm that the number of stuck KYC applications in MongoDB has decreased.
- Check the Kafka consumer lag to ensure it is within acceptable limits.
- Verify that new merchant applications are processing through the KYC stage without delays.

## Escalation

If the issue is not resolved within 60 minutes, escalate to `pagerduty-delta`. Include all diagnostic information and steps taken so far in the escalation notes.
