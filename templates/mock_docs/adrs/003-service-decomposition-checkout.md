---
id: ADR-003
title: Service decomposition strategy for checkout
status: Accepted
date: 2021-01-15
authors: [team-alpha]
services: [checkout-service]
---

# Service decomposition strategy for checkout

## Context

PayLane, originally founded as a monolithic e-commerce platform, faced significant challenges with scalability and reliability, particularly highlighted during a major outage on Black Friday 2020. The monolithic architecture hindered rapid development and deployment, leading to increased downtime and operational complexity. To address these issues, a strategic decision was made to decompose the monolith into microservices, starting with the critical `checkout-service`, which is central to our payment processing capabilities.

## Decision

We decided to extract the `checkout-service` from the monolithic application into an independent microservice written in Go. This service is responsible for managing the checkout process, including session creation and status polling. The `checkout-service` will utilize PostgreSQL on RDS for its primary database and will be deployed on AWS EKS to leverage Kubernetes' orchestration capabilities.

## Consequences

- **Positive:**
  - **Scalability:** The `checkout-service` can scale independently, allowing us to handle increased load during peak times without affecting other parts of the application.
  - **Reliability:** Isolating the checkout logic reduces the risk of a single point of failure impacting the entire platform.
  - **Development Velocity:** Teams can develop, test, and deploy the `checkout-service` independently, accelerating feature delivery and bug fixes.

- **Negative:**
  - **Initial Complexity:** The transition introduces complexity in terms of service orchestration and inter-service communication.
  - **Operational Overhead:** Requires investment in observability and monitoring tools to manage and maintain multiple services effectively.

## Alternatives Considered

- **Maintain Monolith:** Rejected due to scalability and reliability issues that were already impacting business operations.
- **Partial Decomposition:** Considered decomposing only non-critical services, but rejected as it would not address the core scalability issues with the checkout process.
- **Third-party Checkout Solutions:** Rejected due to loss of control over critical payment processes and potential compliance risks.
