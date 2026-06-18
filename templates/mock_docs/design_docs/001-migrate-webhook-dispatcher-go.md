---
id: DD-001
title: Migrate webhook-dispatcher from Python to Go
status: Proposed
date: 2025-01-15
authors: [team-beta]
services: [webhook-dispatcher]
---

# Migrate webhook-dispatcher from Python to Go

## Goal

The primary goal of this design document is to outline the migration of the `webhook-dispatcher` service from Python to Go. This migration aims to improve the service's throughput and reduce latency, leveraging Go's performance advantages over Python. The migration is also expected to align with the company's strategic direction of standardizing new services in Go.

## Non-Goals

- This migration will not introduce new features or change the existing functionality of the `webhook-dispatcher` service.
- It will not address any architectural changes beyond the language migration.
- The migration will not impact other services dependent on the `webhook-dispatcher`.

## Proposal

The `webhook-dispatcher` service currently handles the dispatching of webhooks to merchants. The service is critical in ensuring timely notifications and updates to merchants about various events. Migrating this service to Go is proposed to take advantage of Go's concurrency model and lower resource consumption.

### Architecture Overview

- **Current State:** The service is implemented in Python and uses Redis for queuing.
- **Proposed State:** Re-implement the service in Go, maintaining the current architecture but optimizing for Go's concurrency. The Redis queue will remain unchanged.
- **Performance Improvements:** Go's goroutines will replace Python's threading model, providing more efficient parallel processing of webhook dispatch tasks.

## API / Schema Changes

There are no anticipated changes to the API endpoints or data schemas as part of this migration. The service will continue to expose the `POST /api/v1/webhooks/dispatch` endpoint with the same request and response formats.

## Migration Plan

The migration will be executed in phases:

1. **Development Phase:** Implement the Go version of the service, ensuring feature parity with the existing Python implementation.
2. **Testing Phase:** Conduct thorough testing in a staging environment to validate performance improvements and ensure no regressions.
3. **Deployment Phase:** Deploy the Go version to production in a blue/green deployment model to minimize risk.
4. **Monitoring Phase:** Monitor the service closely using Datadog to ensure performance metrics meet expectations.

## Risks

- **Performance Regression:** There is a risk of performance issues if the Go implementation is not optimized properly.
- **Operational Overhead:** The migration may introduce temporary operational overhead during the transition period.
- **Resource Utilization:** Incorrect configuration of Go's concurrency model could lead to suboptimal resource usage.

## Open Questions

- What specific metrics should be monitored post-deployment to ensure the migration's success?
- Are there any additional dependencies or libraries needed for the Go implementation that need to be evaluated?
- How will the team ensure that all edge cases are covered in the new implementation?
