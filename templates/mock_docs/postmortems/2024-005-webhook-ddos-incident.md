---
id: PM-2024-005
title: Single merchant DDOS via webhook flood saturating webhook-dispatcher
status: Accepted
date: 2024-06-15
authors: [team-beta]
services: [webhook-dispatcher]
related_to: [PM-2024-004]
---

# Single merchant DDOS via webhook flood saturating webhook-dispatcher

## Summary

On June 15, 2024, a single merchant inadvertently initiated a Distributed Denial of Service (DDOS) attack on the `webhook-dispatcher` service by flooding it with a high volume of webhook requests. This resulted in service saturation and delayed webhook processing for approximately 2 hours.

## Impact

The incident caused a significant delay in webhook processing across our platform, affecting all merchants relying on timely webhook notifications. The backlog led to processing delays of up to 2 hours, impacting real-time transaction updates and potentially delaying merchant responses to customer actions. No data was lost, but the delay in communication could have affected merchant operations and customer satisfaction.

## Timeline

- **2024-06-15 10:00 UTC**: The webhook flood began, initiated by a single merchant.
- **2024-06-15 10:15 UTC**: Monitoring alerts triggered due to increased latency in `webhook-dispatcher`.
- **2024-06-15 10:30 UTC**: On-call engineer from Team Beta began investigating the issue.
- **2024-06-15 11:00 UTC**: Identified the source of the flood as a single merchant's misconfigured system.
- **2024-06-15 11:15 UTC**: Throttling rules implemented to mitigate the immediate impact.
- **2024-06-15 12:00 UTC**: Service returned to normal operation with backlog cleared.

## Root Cause

The root cause was a misconfiguration in a merchant's system that resulted in an excessive number of webhook requests being sent to our `webhook-dispatcher`. The service was not equipped with adequate rate limiting to handle such a flood, leading to saturation and delayed processing.

## What Went Well

- The monitoring systems effectively detected the anomaly early, allowing for a prompt investigation.
- The on-call engineer quickly identified the source of the problem and implemented a temporary fix to mitigate the impact.
- Communication with the affected merchant was swift, allowing them to correct the misconfiguration promptly.

## What Went Wrong

- The `webhook-dispatcher` lacked sufficient rate limiting controls to prevent a single merchant from overwhelming the service.
- Initial response time to implement throttling was slower than desired due to the lack of predefined rate limiting policies.

## Action Items

1. **Implement Rate Limiting**
   - **Owner:** Team Beta
   - **Due:** 2024-Q3
   - **Description:** Develop and deploy rate limiting controls to prevent similar incidents in the future.

2. **Enhance Monitoring and Alerts**
   - **Owner:** Team Beta
   - **Due:** 2024-Q3
   - **Description:** Improve alerting mechanisms to detect and respond to potential DDOS patterns more rapidly.

3. **Merchant Communication Protocols**
   - **Owner:** Team Delta
   - **Due:** 2024-Q3
   - **Description:** Establish clearer communication protocols with merchants regarding webhook usage and best practices.

4. **Incident Response Training**
   - **Owner:** Team Beta
   - **Due:** 2024-Q4
   - **Description:** Conduct training sessions for on-call engineers to improve response times and effectiveness in similar situations.
