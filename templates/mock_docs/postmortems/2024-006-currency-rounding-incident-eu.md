---
id: PM-2024-006
title: Currency rounding incident impacting EU merchants
status: Accepted
date: 2024-07-15
authors: [team-sigma]
services: [ledger-service]
related_to: [PM-2024-008]
---

# Currency rounding incident impacting EU merchants

## Summary

On July 15, 2024, a currency rounding issue in the `ledger-service` resulted in incorrect settlement amounts for EU merchants. The incident was caused by a half-cent truncation error in the currency conversion logic.

## Impact

The incident affected approximately 2,500 EU merchants, leading to minor discrepancies in settlement amounts. The issue persisted for 6 hours, from 08:00 to 14:00 UTC, until a hotfix was deployed. The financial impact was minimal, but it required manual reconciliation efforts by affected merchants.

## Timeline

- **2024-07-15 08:00 UTC:** Incident begins; half-cent rounding error introduced during settlement calculations.
- **2024-07-15 09:30 UTC:** First merchant complaint received regarding incorrect settlement amounts.
- **2024-07-15 10:00 UTC:** Incident escalated to `team-sigma` via PagerDuty.
- **2024-07-15 11:00 UTC:** Root cause identified as a truncation error in the currency conversion logic.
- **2024-07-15 12:30 UTC:** Hotfix developed and tested in staging.
- **2024-07-15 13:30 UTC:** Hotfix deployed to production.
- **2024-07-15 14:00 UTC:** Incident resolved; affected merchants notified.

## Root Cause

The root cause was a truncation error in the currency conversion function within the `ledger-service`. The function incorrectly rounded down fractional cent values, leading to cumulative discrepancies in settlement amounts.

## What Went Well

- Rapid identification of the root cause by `team-sigma`, leveraging Datadog metrics and logs.
- Quick development and deployment of a hotfix, minimizing the duration of the impact.
- Effective communication with affected merchants, maintaining trust and transparency.

## What Went Wrong

- The currency conversion logic lacked sufficient precision checks, leading to the truncation error.
- Insufficient automated test coverage for edge cases in currency conversion.
- Delayed detection of the issue due to reliance on merchant complaints rather than proactive monitoring.

## Action Items

- **Improve Test Coverage:** Expand automated tests to cover edge cases in currency conversion. **Owner:** `team-sigma`. **Due:** 2024-Q3.
- **Enhance Monitoring:** Implement proactive monitoring for currency conversion discrepancies. **Owner:** `team-sigma`. **Due:** 2024-Q3.
- **Precision Audit:** Conduct a precision audit of all financial calculations in the `ledger-service`. **Owner:** `team-sigma`. **Due:** 2024-Q4.
