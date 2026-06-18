---
id: PM-2024-008
title: Ledger-service double-entry bug causing settlement drift
status: Accepted
date: 2024-10-15
authors: [team-sigma]
services: [ledger-service]
---

# Ledger-service double-entry bug causing settlement drift

## Summary

On October 10, 2024, a double-entry bug in the `ledger-service` caused settlement drift, impacting the accuracy of financial records for several hours.

## Impact

The bug affected the ledger's ability to correctly record transactions, leading to discrepancies in settlement reports. Approximately 2,000 transactions were affected, resulting in incorrect balances for merchants. The issue lasted for 4 hours, from 10:00 to 14:00 UTC, before being resolved. No financial losses were reported, but the incident required manual reconciliation efforts.

## Timeline

- **2024-10-10 10:00 UTC**: Anomaly detected in settlement reports by the finance team.
- **2024-10-10 10:15 UTC**: Incident escalated to Team Sigma via PagerDuty.
- **2024-10-10 10:30 UTC**: Initial investigation begins; logs from `ledger-service` are reviewed.
- **2024-10-10 11:00 UTC**: Root cause identified as a bug in the double-entry logic.
- **2024-10-10 11:30 UTC**: Temporary fix deployed to correct the logic error.
- **2024-10-10 12:00 UTC**: Manual reconciliation process initiated for affected transactions.
- **2024-10-10 14:00 UTC**: Issue fully resolved; all transactions reconciled.

## Root Cause

The issue was caused by a logic error in the double-entry accounting system of the `ledger-service`. A recent update inadvertently introduced a bug where certain transactions were recorded twice, leading to incorrect balance calculations.

## What Went Well

- The finance team quickly detected the anomaly, allowing for prompt escalation.
- Team Sigma efficiently identified and isolated the bug within the `ledger-service`.
- A temporary fix was rapidly deployed, minimizing the duration of the impact.

## What Went Wrong

- The bug was introduced during a recent update without adequate testing.
- Lack of automated tests for double-entry logic allowed the bug to go unnoticed.
- Manual reconciliation was labor-intensive and time-consuming.

## Action Items

1. **Improve Test Coverage**: Enhance automated testing for double-entry logic to prevent similar issues. **Owner: Team Sigma, Due: 2025-Q1**
2. **Code Review Process**: Strengthen code review procedures to catch potential logic errors. **Owner: Team Sigma, Due: 2025-Q1**
3. **Monitoring Enhancements**: Implement additional monitoring for transaction anomalies in the `ledger-service`. **Owner: Team Sigma, Due: 2025-Q2**
