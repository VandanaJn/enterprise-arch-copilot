---
id: PM-2024-003
title: Fraud-detection model regression flagging legitimate transactions
status: Accepted
date: 2024-05-15
authors: [team-sigma]
services: [fraud-detection-service]
---

# Fraud-detection model regression flagging legitimate transactions

## Summary

On April 28, 2024, a regression in the fraud-detection-service v1.7 model caused a significant increase in false-positive fraud flags, affecting legitimate transactions. This issue persisted for approximately 6 hours before the model was rolled back.

## Impact

The regression resulted in legitimate transactions being incorrectly flagged as fraudulent, leading to an increase in declined transactions. Approximately 15% of transactions during the incident window were affected, impacting merchant sales and customer satisfaction. The issue lasted from 09:00 UTC to 15:00 UTC on April 28, 2024.

## Timeline

- **09:00 UTC**: Deployment of fraud-detection-service v1.7 model begins.
- **09:15 UTC**: Increase in fraud flags observed in Datadog metrics; PagerDuty alerts triggered.
- **09:30 UTC**: Team Sigma begins investigation into the anomaly.
- **10:00 UTC**: Initial hypothesis suggests a model regression.
- **11:00 UTC**: Regression confirmed; decision made to roll back to the previous model version.
- **12:00 UTC**: Rollback initiated.
- **13:30 UTC**: Rollback completed; monitoring shows return to normal fraud flag rates.
- **15:00 UTC**: Incident declared resolved after confirming stability.

## Root Cause

The root cause was identified as a regression in the fraud-detection model's feature extraction logic, which inadvertently increased the weight of certain benign transaction patterns, leading to false positives.

## What Went Well

- Monitoring and alerting systems detected the anomaly quickly, allowing for a prompt response.
- The rollback process was executed smoothly, minimizing the duration of the impact.
- Team Sigma effectively collaborated to diagnose and resolve the issue.

## What Went Wrong

- The regression was not caught during pre-deployment testing, indicating a gap in the test coverage for feature extraction changes.
- Communication with affected merchants was delayed, leading to confusion and dissatisfaction.

## Action Items

- **Expand test coverage** for feature extraction logic in fraud-detection models. **Owner: Team Sigma, Due: 2024-Q3**
- **Improve communication protocols** for notifying merchants of ongoing incidents. **Owner: Team Delta, Due: 2024-Q3**
- **Conduct a post-incident review** to identify further improvements in the model deployment process. **Owner: Team Sigma, Due: 2024-Q2**
