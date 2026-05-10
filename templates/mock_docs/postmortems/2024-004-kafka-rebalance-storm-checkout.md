---
id: PM-2024-004
title: Kafka rebalance storm on checkout.events
status: Accepted
date: 2024-03-15
authors: [team-alpha]
services: [checkout-service]
---

# Kafka rebalance storm on checkout.events

## Summary
On March 14, 2024, a Kafka rebalance storm on the `checkout.events` topic caused a 5-minute pause in consumer processing, impacting the `checkout-service`.

## Impact
The incident resulted in a temporary delay in processing checkout events, affecting approximately 2,500 transactions. Customers experienced delays in checkout completion, leading to potential cart abandonment. The incident lasted for 5 minutes, with a high severity due to its impact on the critical payment path.

## Timeline
- **2024-03-14 15:00 UTC**: Automated alert triggered for consumer lag on `checkout.events`.
- **2024-03-14 15:02 UTC**: Team Alpha on-call engineer acknowledged the alert via PagerDuty.
- **2024-03-14 15:03 UTC**: Investigation began, focusing on Kafka consumer metrics in Datadog.
- **2024-03-14 15:05 UTC**: Identified significant consumer lag and rebalance activity.
- **2024-03-14 15:07 UTC**: Temporarily increased consumer group partitions to stabilize processing.
- **2024-03-14 15:10 UTC**: Consumer lag resolved, and normal processing resumed.

## Root Cause
The root cause was identified as an unexpected increase in partition rebalances triggered by a misconfigured consumer group setting. This setting caused excessive rebalancing when a new consumer joined the group, leading to a temporary halt in event processing.

## What Went Well
- The alerting system effectively notified the on-call engineer immediately, reducing the time to detect the issue.
- The team quickly identified the root cause using Datadog's comprehensive metrics.
- The temporary increase in partitions was swiftly implemented, allowing for rapid recovery.

## What Went Wrong
- The consumer group configuration was not adequately tested under high load scenarios, leading to unexpected rebalancing behavior.
- Documentation on Kafka consumer settings was insufficient, leading to misconfiguration.

## Action Items
- **Team Alpha**: Review and update Kafka consumer group configurations to prevent excessive rebalancing. **Due: 2024-Q2**
- **Team Alpha**: Enhance documentation on Kafka consumer settings and conduct training sessions. **Due: 2024-Q2**
- **Team Alpha**: Implement automated tests for consumer group settings under load. **Due: 2024-Q3**
