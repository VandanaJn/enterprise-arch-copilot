---
id: PM-2024-001
title: Black Friday 2024 checkout-service outage during peak traffic
status: Accepted
date: 2024-11-30
authors: [team-alpha]
services: [checkout-service]
---

# Black Friday 2024 checkout-service outage during peak traffic

## Summary
On Black Friday 2024, the `checkout-service` experienced an outage during peak traffic, resulting in failed checkout attempts for a significant number of customers. The incident lasted approximately 30 minutes and was resolved by scaling the service and optimizing database queries.

## Impact
The outage affected the checkout process for approximately 15% of transactions during the peak hour, leading to an estimated $500,000 in lost revenue. The service was unavailable from 18:00 to 18:30 UTC, causing significant customer dissatisfaction and impacting our reputation during a critical sales period.

## Timeline
- **18:00 UTC**: Checkout failures begin, alerts triggered in Datadog.
- **18:05 UTC**: Team Alpha on-call engineer acknowledges PagerDuty alert.
- **18:10 UTC**: Initial investigation points to database query latency.
- **18:15 UTC**: Traffic surge identified as root cause of query latency.
- **18:20 UTC**: Temporary scaling of `checkout-service` and database replicas initiated.
- **18:25 UTC**: Query optimizations applied to reduce load.
- **18:30 UTC**: Service restored and monitoring for stability.

## Root Cause
The root cause of the outage was a combination of insufficient database indexing and suboptimal query performance under high traffic conditions. The surge in traffic during Black Friday exceeded the anticipated load, leading to increased query latency and service degradation.

## What Went Well
- The on-call engineer responded promptly to the alert and began troubleshooting within 5 minutes.
- Scaling the service and database replicas provided immediate relief, allowing for a quick recovery.
- Communication between team members was effective, ensuring a coordinated response.

## What Went Wrong
- The database was not adequately prepared for the anticipated Black Friday traffic, lacking necessary indexes to handle the load efficiently.
- Monitoring thresholds were not calibrated to detect early signs of query performance degradation under peak conditions.

## Action Items
- **Team Alpha**: Implement comprehensive database indexing strategy by 2025-Q1.
- **Team Alpha**: Review and update traffic forecasting models for peak events by 2025-Q1.
- **Team Alpha**: Enhance monitoring and alerting for database performance metrics by 2025-Q1.
- **Team Alpha**: Conduct a post-event traffic simulation to validate improvements by 2025-Q2.
