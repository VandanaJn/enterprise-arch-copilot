# ADR 002: Migrate Checkout Service to AWS EKS
        
**Status:** Accepted
**Date:** 2024-01-10

## Context
The `checkout-service` requires high elasticity during peak holiday shopping.

## Decision
We will migrate the `checkout-service` from on-premise VMs to AWS Elastic Kubernetes Service (EKS).

## Consequences
- Faster auto-scaling during traffic spikes.
- Requires team training on Kubernetes deployment manifests.
