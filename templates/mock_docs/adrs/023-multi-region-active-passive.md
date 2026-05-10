---
id: ADR-023
title: Multi-region active-passive disaster recovery
status: Accepted
date: 2024-01-15
authors: [team-alpha, team-sigma]
services: [checkout-service, payment-gateway-service, ledger-service]
related_to: [ADR-004, ADR-018]
---

# Multi-region active-passive disaster recovery

## Context

PayLane processes transactions for over 12,000 SMB merchants across North America and Europe. Ensuring high availability and disaster recovery (DR) capabilities is critical to maintaining our 99.99% SLO for tier-0 services like `checkout-service`, `payment-gateway-service`, and `ledger-service`. Currently, these services are deployed in a single AWS region, which poses a risk of significant downtime in the event of a regional outage.

## Decision

We will implement a multi-region active-passive disaster recovery strategy. The primary region will continue to handle all production traffic, while a secondary region will be configured as a hot standby. In the event of a failure in the primary region, traffic will be rerouted to the secondary region with minimal downtime.

Key components of the strategy include:
- **Data Replication**: Use AWS RDS cross-region replication for PostgreSQL databases and S3 cross-region replication for object storage.
- **Infrastructure as Code**: Leverage Terraform to manage infrastructure in both regions, ensuring consistency.
- **Automated Failover**: Implement Route 53 health checks and failover routing policies to automatically redirect traffic.
- **Regular DR Drills**: Conduct quarterly disaster recovery drills to test and validate failover processes.

## Consequences

- **Positive**:
  - Enhances resilience against regional outages, improving service reliability.
  - Reduces potential downtime, aligning with our 99.99% SLO for tier-0 services.
  - Provides a tested and repeatable process for disaster recovery.

- **Negative**:
  - Increases operational complexity and cost due to maintaining infrastructure in a secondary region.
  - Requires ongoing monitoring and management to ensure synchronization between regions.

## Alternatives Considered

- **Single-region DR**: Rejected due to insufficient protection against regional outages.
- **Multi-region Active-Active**: Rejected due to higher complexity and cost, not justified by current traffic levels.
- **Cold Standby**: Rejected as it results in longer recovery times, not meeting our SLO requirements.
