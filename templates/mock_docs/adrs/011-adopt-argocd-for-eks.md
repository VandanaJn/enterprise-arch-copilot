---
id: ADR-011
title: Adopt ArgoCD for EKS GitOps deploys
status: Accepted
date: 2023-06-15
authors: [team-alpha, team-delta]
services: [checkout-service, merchant-onboarding-service]
related_to: [ADR-004, ADR-006]
---

# Adopt ArgoCD for EKS GitOps deploys

## Context

As PayLane transitions its infrastructure to AWS EKS, managing deployments efficiently and reliably becomes crucial. Our current deployment process involves manual steps that are prone to errors and inconsistencies, especially as the number of services grows. To address these challenges, we need a GitOps-based deployment solution that automates and standardizes the deployment process across all services hosted on EKS.

## Decision

We will adopt ArgoCD as our GitOps tool for managing deployments to AWS EKS. ArgoCD will enable us to automate the deployment process by synchronizing the desired state defined in Git repositories with the actual state in our Kubernetes clusters. This decision aligns with our strategy to improve deployment reliability and reduce manual intervention.

## Consequences

- **Positive:**
  - **Improved Consistency:** ArgoCD ensures that the deployed state matches the state defined in Git, reducing configuration drift.
  - **Increased Deployment Speed:** Automating deployments reduces the time and effort required to release new features and updates.
  - **Enhanced Visibility:** The ArgoCD dashboard provides a clear view of the deployment status and history, aiding in troubleshooting and audits.

- **Negative:**
  - **Learning Curve:** Teams will need to familiarize themselves with ArgoCD and GitOps principles, requiring training and adaptation time.
  - **Initial Setup Effort:** Integrating ArgoCD with existing CI/CD pipelines and Kubernetes clusters will require initial setup and configuration effort.

## Alternatives Considered

- **Jenkins X:** Rejected due to its complexity and additional overhead in managing Jenkins instances.
- **FluxCD:** Rejected because it lacks the comprehensive UI and user experience provided by ArgoCD, which is important for our teams' operational efficiency.
- **Manual Deployments:** Rejected as they do not scale well with our growing number of services and increase the risk of human error.
