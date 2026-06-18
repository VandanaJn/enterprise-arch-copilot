# PayLane Engineering — Company Spec

> This document is the single source of truth for the fictional engineering organization
> behind the Enterprise Architecture Copilot. It seeds LLM-driven generation of ADRs,
> runbooks, postmortems, and design docs (see `scripts/generate_corpus.py`). Every
> generated document must be consistent with the facts here.

## Company

- **Name:** PayLane
- **Founded:** 2019-Q3 (originally **PayLane Commerce** — an end-to-end e-commerce + payments platform)
- **Pivot:** 2022-Q2 — repositioned as a **pure payment-processing SaaS for SMB merchants**. The legacy inventory & catalog code remains as a sunset domain.
- **Customers:** ~12,000 SMB merchants in NA + EU, processing ~$4B GMV/year
- **HQ:** Toronto + remote
- **Compliance:** PCI-DSS Level 1, SOC 2 Type II

## Tech stack

- **Languages:** Go (most services), Python (ML & data), Kotlin/JVM (ledger), TypeScript/Node (merchant-facing UI services)
- **Datastores:** PostgreSQL (primary OLTP), TimescaleDB (ledger time-series), ClickHouse (analytics), MongoDB (merchant onboarding), Redis (caching, queues)
- **Streaming:** Apache Kafka (since 2022-Q3, replacing RabbitMQ)
- **Cloud:** AWS — EKS for compute, RDS for Postgres, S3, KMS, Secrets Manager
- **Observability:** Datadog (metrics, APM), Loki (logs), PagerDuty (paging), Sentry (errors)
- **CI/CD:** GitHub Actions, ArgoCD for EKS deploys

## Teams

| Team | Mission | On-call rotation |
|---|---|---|
| Team Alpha | Checkout & Payments — the critical path from card swipe to authorization | `pagerduty-alpha` |
| Team Beta | Identity & Communications — buyer accounts, notifications, webhooks | `pagerduty-beta` |
| Team Gamma | Legacy Commerce — winding down inventory/catalog domain (sunset 2025-Q3) | `pagerduty-gamma` |
| Team Sigma | Risk & Ledger — fraud ML, double-entry accounting, settlement | `pagerduty-sigma` |
| Team Delta | Merchant Experience — onboarding, reporting, dashboards | `pagerduty-delta` |

## Services

| Name | Owner | Language | Primary DB | Tier | Status |
|---|---|---|---|---|---|
| `checkout-service` | Team Alpha | Go | PostgreSQL (RDS) | tier-0 | active |
| `payment-gateway-service` | Team Alpha | Go | PostgreSQL (RDS) | tier-0 | active |
| `fraud-detection-service` | Team Sigma | Python | Redis + S3 (model artifacts) | tier-0 | active |
| `ledger-service` | Team Sigma | Kotlin | TimescaleDB | tier-0 | active |
| `user-profile-service` | Team Beta | Python | PostgreSQL (RDS) | tier-1 | active |
| `notification-service` | Team Beta | Python | Redis only | tier-1 | active |
| `webhook-dispatcher` | Team Beta | Go | Redis | tier-1 | active |
| `merchant-onboarding-service` | Team Delta | TypeScript / Node | MongoDB | tier-2 | active |
| `reporting-service` | Team Delta | Python | ClickHouse | tier-2 | active |
| `legacy-inventory-service` | Team Gamma | Go | PostgreSQL (RDS) | tier-2 | **deprecated** — sunset 2025-Q3 |

Tier definitions:
- **tier-0**: customer-facing critical path. Outage = lost revenue per minute. 99.99% SLO.
- **tier-1**: user-facing but not on the critical path. 99.9% SLO.
- **tier-2**: internal or non-real-time. 99.5% SLO.

## Sample API endpoints

- `POST /api/v1/checkout` (`checkout-service`) — Create a new checkout session
- `GET /api/v1/checkout/{id}/status` (`checkout-service`) — Poll status
- `POST /api/v1/payments/authorize` (`payment-gateway-service`) — Authorize a card
- `POST /api/v1/payments/capture` (`payment-gateway-service`) — Capture an authorized payment
- `POST /api/v1/payments/refund` (`payment-gateway-service`) — Issue a refund
- `POST /api/v1/fraud/score` (`fraud-detection-service`) — Score a transaction
- `GET /api/v1/users/profile` (`user-profile-service`) — Retrieve buyer profile
- `POST /api/v1/users` (`user-profile-service`) — Create a buyer account
- `POST /api/v1/notifications/send` (`notification-service`) — Send transactional email/SMS
- `POST /api/v1/webhooks/dispatch` (`webhook-dispatcher`) — Dispatch a merchant webhook
- `POST /api/v1/merchants/onboard` (`merchant-onboarding-service`) — Begin merchant KYC
- `GET /api/v1/reports/transactions` (`reporting-service`) — Pull a transactions report
- `GET /api/v1/inventory/check` (`legacy-inventory-service`) — **DEPRECATED** stock check

## Engineering timeline

| Date | Event |
|---|---|
| 2019-Q3 | Company founded as PayLane Commerce. Single Rails monolith. |
| 2020-Q4 | First major Black Friday outage. Monolith pain becomes real. |
| 2021-Q1 | Service decomposition begins. `checkout-service` extracted first (Go). |
| 2021-Q3 | `user-profile-service` and `notification-service` extracted. Still on RabbitMQ. |
| 2022-Q2 | **Pivot** to pure payments SaaS. `legacy-inventory-service` marked for eventual sunset. New domains: payment-gateway, fraud-detection, ledger. |
| 2022-Q3 | Kafka adoption (replaces RabbitMQ for new event streams). |
| 2023-Q1 | AWS EKS migration begins; checkout-service first to migrate. |
| 2023-Q4 | Fraud-detection ML platform v1 ships (Python + Redis feature store). |
| 2024-Q2 | Ledger rewrite to Kotlin + TimescaleDB for double-entry correctness. |
| 2024-Q4 | PCI-DSS recertification — driving several security/compliance ADRs. |
| 2025-Q1 | Webhook-dispatcher rewrite from Python to Go for throughput. |
| 2025-Q3 | Planned: complete sunset of `legacy-inventory-service`. |

## Cross-reference rules

Generated documents MUST follow these conventions so the agent can reason across them:

- **ADR ID format:** `ADR-NNN` (3-digit, zero-padded). Filenames: `templates/mock_docs/adrs/NNN-short-slug.md`
- **Runbook ID format:** `RB-NNN`. Filenames: `templates/mock_docs/runbooks/NNN-short-slug.md`
- **Postmortem ID format:** `PM-YYYY-NNN`. Filenames: `templates/mock_docs/postmortems/YYYY-NNN-short-slug.md`
- **Design doc ID format:** `DD-NNN`. Filenames: `templates/mock_docs/design_docs/NNN-short-slug.md`

### YAML frontmatter (required on every doc)

```yaml
---
id: ADR-007
title: Adopt Kafka for event streaming
status: Accepted              # one of: Proposed, Accepted, Deprecated, Superseded
date: 2022-08-12
authors: [team-alpha, team-sigma]
services: [checkout-service, payment-gateway-service]
supersedes: [ADR-003]         # optional; list of IDs this replaces
superseded_by: ADR-019        # optional; the ID that replaced this one
related_to: [RB-004, DD-002]  # optional
---
```

### Supersession chains

At least one ADR chain must exist where ADR-A is **superseded by** ADR-B (e.g. RabbitMQ → Kafka). The agent should be able to answer "what is the current event-streaming choice" by following the chain to the latest non-superseded ADR.

### Deprecation markers

`legacy-inventory-service` should be referenced in some ADRs/runbooks with explicit deprecation language ("scheduled for sunset 2025-Q3"). Queries about it should return current information including the deprecation status.

## Topics for generated docs (suggested coverage)

The generation script should aim for breadth across these topics so the corpus exercises retrieval:

**ADRs** (~25): event streaming choice (RabbitMQ → Kafka), service decomposition, AWS EKS migration, multi-region strategy, fraud ML platform, ledger rewrite to Kotlin, observability stack, CI/CD on ArgoCD, secret management with KMS, PCI-DSS network segmentation, deprecation of inventory-service, language standardization (Go for new services), contract testing strategy, webhook retry semantics, idempotency keys, schema registry adoption, blue/green deployments, feature flagging vendor, frontend monorepo decision, datastore choices, on-call rotation policy, error budgeting, postmortem process formalization, rate limiting at the edge, API versioning strategy.

**Runbooks** (~15): checkout 504 mitigation, payment-gateway timeouts, fraud-detection model fallback, ledger reconciliation drift, user-profile DB failover, Kafka consumer lag spike, webhook dispatch backlog, merchant onboarding stuck in KYC, ClickHouse query slowness, EKS pod evictions, RDS connection exhaustion, Redis memory pressure, certificate expiry, secrets rotation, deploy rollback.

**Postmortems** (~8): a Black Friday checkout outage, a payment-gateway-service Stripe credential incident, a fraud-detection model regression, a ledger double-entry bug, a Kafka rebalance storm, a webhook flood DDOSing a merchant, a deploy that wedged the EKS cluster, a config-driven currency-rounding incident.

**Design docs** (~5): proposed migration of webhook-dispatcher to Go, fraud-detection v2 architecture, multi-region active-active proposal, sunset plan for legacy-inventory-service, observability v2 (OTel adoption).
