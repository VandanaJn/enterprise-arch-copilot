---
id: ADR-008
title: Secret management via AWS KMS and Secrets Manager
status: Accepted
date: 2023-02-15
authors: [team-alpha, team-delta]
services: [checkout-service, merchant-onboarding-service]
---

# Secret management via AWS KMS and Secrets Manager

## Context

As PayLane continues to scale its services and infrastructure, managing sensitive information such as API keys, database credentials, and encryption keys securely becomes increasingly critical. Historically, secrets were managed through environment variables and configuration files, which pose security risks and complicate secret rotation. To enhance security and streamline secret management, we propose adopting AWS Key Management Service (KMS) and AWS Secrets Manager.

## Decision

PayLane will adopt AWS KMS and AWS Secrets Manager for managing all sensitive information across services. AWS KMS will be used for encryption key management, while AWS Secrets Manager will handle the storage, retrieval, and rotation of secrets such as database credentials and API keys.

## Consequences

- **Positive:**
  - **Enhanced Security:** Secrets are stored securely and encrypted using AWS KMS, reducing the risk of exposure.
  - **Automated Rotation:** AWS Secrets Manager supports automated secret rotation, minimizing manual intervention and reducing the risk of expired credentials.
  - **Centralized Management:** A single platform for managing secrets across all services simplifies administration and auditing.
  - **Integration with AWS Services:** Seamless integration with AWS services such as RDS and EKS improves operational efficiency.

- **Negative:**
  - **Cost:** AWS Secrets Manager incurs additional costs, especially with frequent secret rotations.
  - **Complexity:** Initial setup and migration from existing secret management practices require effort and coordination across teams.

## Alternatives Considered

- **Environment Variables:** Rejected due to security risks and lack of automated rotation.
- **HashiCorp Vault:** Offers robust features but adds operational overhead and complexity compared to AWS-native solutions.
- **Custom Secret Management Solution:** Rejected due to the high development and maintenance burden.

Adopting AWS KMS and Secrets Manager aligns with PayLane's commitment to security and operational efficiency, providing a scalable and secure solution for managing sensitive information across our growing infrastructure.
