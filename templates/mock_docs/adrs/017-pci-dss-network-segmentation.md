---
id: ADR-017
title: Adopt PCI-DSS network segmentation strategy
status: Accepted
date: 2024-02-15
authors: [team-alpha, team-sigma]
services: [checkout-service, payment-gateway-service, fraud-detection-service, ledger-service]
related_to: [ADR-012, ADR-008]
---

# Adopt PCI-DSS network segmentation strategy

## Context

PayLane, as a payment-processing SaaS, must adhere to PCI-DSS Level 1 compliance requirements. As part of our ongoing efforts to maintain compliance and enhance security, a robust network segmentation strategy is essential. This strategy aims to isolate cardholder data environments (CDE) from non-CDE systems, minimizing the scope of PCI-DSS audits and reducing potential attack vectors.

## Decision

We will implement a network segmentation strategy that clearly delineates CDE from non-CDE systems. This involves:

- Using Virtual Private Clouds (VPCs) to separate environments.
- Applying strict security group policies to control access between CDE and non-CDE systems.
- Implementing network access control lists (ACLs) to further restrict traffic.
- Utilizing AWS KMS for encryption of data in transit and at rest.

This decision ensures that only authorized services, such as `checkout-service`, `payment-gateway-service`, `fraud-detection-service`, and `ledger-service`, have access to the CDE, thereby maintaining a high security standard.

## Consequences

- **Positive:**
  - Enhanced security posture by reducing the attack surface.
  - Simplified PCI-DSS audit process due to reduced scope.
  - Improved data protection for cardholder information.

- **Negative:**
  - Initial complexity and cost in setting up and maintaining segmented networks.
  - Potential for increased latency due to network isolation.

## Alternatives Considered

- **Flat Network Architecture:** Rejected due to increased risk of non-compliance and higher vulnerability to attacks.
- **Logical Segmentation via Tags:** Rejected as it provides insufficient isolation for PCI-DSS requirements.
- **Full Physical Segmentation:** Rejected due to impracticality and excessive cost in a cloud environment.
