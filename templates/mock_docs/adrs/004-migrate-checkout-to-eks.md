---
id: ADR-004
title: Migrate checkout-service to AWS EKS
status: Accepted
date: 2023-02-15
authors: [team-alpha]
services: [checkout-service]
related_to: [ADR-003]
---

# Migrate checkout-service to AWS EKS

## Context

The `checkout-service` is a critical component of PayLane's payment processing pipeline, responsible for handling checkout sessions. As part of our ongoing efforts to improve scalability, reliability, and operational efficiency, we have decided to migrate the `checkout-service` to AWS Elastic Kubernetes Service (EKS). This migration aligns with our broader strategy to leverage Kubernetes for orchestration and management of containerized workloads, as outlined in our service decomposition strategy (see ADR-003).

## Decision

We will migrate the `checkout-service` from its current deployment environment to AWS EKS. This decision is driven by the need to enhance our deployment capabilities, improve resource utilization, and streamline operations through Kubernetes-native tools and practices.

## Consequences

**Positive:**
- **Scalability:** EKS provides native support for auto-scaling, allowing us to dynamically adjust resources based on traffic patterns.
- **Reliability:** Kubernetes offers robust self-healing capabilities, reducing downtime by automatically replacing failed pods.
- **Operational Efficiency:** EKS integrates with AWS services, simplifying monitoring and logging through tools like Datadog and Loki.
- **Consistency:** Standardizing on Kubernetes across services ensures consistent deployment and management practices.

**Negative:**
- **Complexity:** Kubernetes introduces additional complexity in managing configurations and deployments.
- **Learning Curve:** Teams need to ramp up on Kubernetes concepts and AWS-specific integrations.
- **Cost:** Potential increase in AWS costs due to EKS pricing and resource consumption.

## Alternatives Considered

- **Remain on current infrastructure:** Rejected due to limitations in scalability and operational overhead.
- **Use a different Kubernetes provider:** Rejected as EKS offers the best integration with our existing AWS infrastructure.
- **Adopt a serverless architecture:** Rejected due to the need for fine-grained control over the deployment environment and resource allocation.
