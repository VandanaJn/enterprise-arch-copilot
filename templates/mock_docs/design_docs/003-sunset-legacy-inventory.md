---
id: DD-003
title: Sunset plan for legacy-inventory-service
status: Proposed
date: 2024-03-15
authors: [team-gamma]
services: [legacy-inventory-service]
---

# Sunset plan for legacy-inventory-service

## Goal

The goal of this design document is to outline a comprehensive plan for sunsetting the `legacy-inventory-service`. This service is part of the old PayLane Commerce platform and is scheduled for deprecation by 2025-Q3. The sunset plan aims to ensure a smooth transition for any remaining dependencies and to decommission the service without impacting current operations.

## Non-Goals

- This document does not cover the migration of data from the `legacy-inventory-service` to any new systems.
- It does not address the development of new features or enhancements for existing systems.
- It does not include the sunset plans for other legacy services.

## Proposal

The `legacy-inventory-service` is a tier-2 service currently in a deprecated state. The proposal involves a phased approach to decommissioning:

1. **Dependency Audit**: Identify all systems and processes that still rely on the `legacy-inventory-service`. This includes checking integrations with other services and external merchant dependencies.

2. **Communication Plan**: Notify all stakeholders, including merchants and internal teams, about the sunset timeline and any necessary actions they need to take.

3. **Data Archival**: Ensure all necessary data is archived in compliance with regulatory requirements. This involves exporting data to a long-term storage solution, such as AWS S3.

4. **Service Decommissioning**: Gradually reduce the operational footprint of the service by scaling down resources and eventually terminating the service in AWS EKS.

5. **Post-Sunset Monitoring**: Implement monitoring to ensure no unexpected issues arise post-decommissioning.

## API / Schema Changes

No new API or schema changes are planned as part of this sunset process. Existing API endpoints will be deprecated and eventually disabled as the service is decommissioned.

## Migration Plan

### Phase 1: Dependency Audit (2024-Q2)
- Conduct a thorough review of all systems interacting with the `legacy-inventory-service`.
- Document any critical dependencies that need alternative solutions.

### Phase 2: Communication and Data Archival (2024-Q3)
- Initiate communication with all affected parties.
- Begin data export and archival processes.

### Phase 3: Service Decommissioning (2025-Q1)
- Scale down service operations and resources.
- Monitor for any issues during the phased shutdown.

### Phase 4: Final Termination and Monitoring (2025-Q3)
- Complete the termination of the service.
- Continue monitoring for any residual issues.

## Risks

- **Data Loss**: There is a risk of data loss if archival processes are not properly validated.
- **Stakeholder Impact**: Inadequate communication may lead to stakeholder dissatisfaction.
- **Operational Disruption**: Unexpected dependencies might cause disruptions if not identified early.

## Open Questions

- Are there any compliance considerations that need additional attention during data archival?
- What is the fallback plan if critical dependencies are identified late in the process?
- How will we handle any merchant-specific customizations tied to the `legacy-inventory-service`?
