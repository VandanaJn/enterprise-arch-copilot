---
id: ADR-013
title: Idempotency keys for payment-gateway endpoints
status: Accepted
date: 2023-09-15
authors: [team-alpha]
services: [payment-gateway-service]
---

# Idempotency keys for payment-gateway endpoints

## Context

The `payment-gateway-service` is a critical component of our payment-processing pipeline, responsible for authorizing, capturing, and refunding payments. Given its tier-0 status, ensuring reliability and consistency in transaction processing is paramount. Duplicate requests can occur due to network retries or client-side errors, potentially leading to double charges or refunds if not handled correctly.

To address this, we propose implementing idempotency keys for the payment-gateway endpoints. This mechanism ensures that multiple identical requests result in only one action being performed, maintaining data integrity and enhancing user trust.

## Decision

We will implement idempotency keys for the following endpoints of the `payment-gateway-service`:
- `POST /api/v1/payments/authorize`
- `POST /api/v1/payments/capture`
- `POST /api/v1/payments/refund`

Clients will include a unique idempotency key in the header of these requests. The service will store the result of the first request associated with each key and return the same result for subsequent requests with the same key.

## Consequences

**Positive:**
- Ensures transaction consistency and prevents duplicate charges or refunds, improving customer trust.
- Reduces the risk of financial discrepancies, aligning with our compliance requirements.
- Enhances the robustness of the `payment-gateway-service` against network retries and client-side errors.

**Negative:**
- Additional storage and processing overhead to manage idempotency keys.
- Potential complexity in handling expired or stale keys, requiring a clear policy for key retention and cleanup.

## Alternatives Considered

- **No idempotency:** Rejected due to high risk of duplicate transactions impacting customer experience and financial integrity.
- **Client-side deduplication:** Rejected as it places the burden on clients, leading to inconsistent implementations and increased complexity for our customers.
