# Sample Questions for Enterprise Architecture Copilot

Paste any of these at the `You:` prompt when running `make run` / `./tasks.ps1 run`.

---

## Factual lookups (SQL retrieval)

- What version is checkout-service currently on?
- Which services are tier-0 critical?
- Are any services deprecated?
- Who owns ledger-service?
- What language is fraud-detection-service written in?
- What's the criticality tier of reporting-service?
- Which services are owned by Team Sigma?
- What's the on-call rotation for Team Beta?
- What endpoints does payment-gateway-service expose?
- What's the repository URL for checkout-service?

---

## Single-hop docs (vector retrieval)

- What ADR covers our Kafka adoption decision?
- Why did we choose Kafka over RabbitMQ?
- What ADR covers the AWS EKS migration of checkout-service?
- Is there a runbook for checkout-service 504 errors?
- What's the plan for sunsetting legacy-inventory-service?
- Why did we adopt Datadog?
- How do we handle Kafka consumer lag spikes?
- What's our policy on idempotency keys for payment endpoints?
- What's our blue/green deployment policy?
- How do we approach PCI-DSS network segmentation?
- Is there a design doc for multi-region active-active?
- What's the design doc for adopting OpenTelemetry?

---

## Multi-hop incident (SQL + docs + synthesis — the main workflow)

- The /api/v1/checkout endpoint is failing with a 504. Who owns it and is there a runbook?
- /api/v1/payments/authorize is timing out — who's on call and what should I do?
- There's Kafka consumer lag on checkout.events — who do I page and what's the mitigation?
- user-profile-service is throwing RDS connection errors — which team and what runbook?
- webhook-dispatcher is backing up — who do I page and what's the fix?
- fraud-detection-service ML cluster is down — what's the fallback procedure?
- notification-service is OOM — what runbook applies and who owns it?
- ClickHouse queries on the reporting service are slow — runbook?
- Was there a recent incident on checkout-service?
- What was the impact of the Black Friday 2024 checkout outage?
- Did ledger-service have any SEV-1 incidents recently?

---

## Ambiguous queries (fuzzy matching)

- Tell me about fraud at PayLane.
- What does the checkout team work on?
- Who handles the ledger?
- Is there a service called 'users'?
- Anything about webhook problems?
- What's our auth API?

---

## Supersession-aware (should follow ADR chains)

- What's our current event-streaming choice?          ← should say Kafka, NOT RabbitMQ
- Are we still using RabbitMQ?                        ← should say No
- What did we use for messaging before Kafka?
- Which ADRs have been superseded?

---

## Out-of-scope (should decline politely)

- What's the weather in San Francisco today?
- Write me a haiku about Mondays.
- How do I make pasta carbonara?
- What's the best programming language overall?
