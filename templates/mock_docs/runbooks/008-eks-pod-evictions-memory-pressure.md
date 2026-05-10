---
id: RB-008
title: EKS pod evictions on tier-0 nodes due to memory pressure
status: Accepted
date: 2024-03-15
authors: [team-alpha]
services: [checkout-service, payment-gateway-service]
---

# EKS pod evictions on tier-0 nodes due to memory pressure

## Symptoms

EKS pods running on tier-0 nodes, specifically those hosting the `checkout-service` and `payment-gateway-service`, are being evicted due to memory pressure. This results in intermittent service disruptions, leading to increased latency and potential transaction failures.

## Diagnostic Steps

1. **Check Pod Eviction Events:**
   - Use `kubectl get events --namespace=<namespace> --field-selector reason=Evicted` to identify pods that have been evicted due to memory pressure.
   - Confirm the affected pods are part of the `checkout-service` or `payment-gateway-service` deployments.

2. **Analyze Resource Usage:**
   - Utilize Datadog dashboards to monitor memory usage trends for the affected nodes.
   - Identify any recent spikes in memory usage that correlate with the eviction events.

3. **Evaluate Node Capacity:**
   - Use `kubectl describe nodes` to check the available memory capacity on the affected nodes.
   - Ensure that the node's memory resources are not overcommitted.

4. **Review Pod Resource Requests and Limits:**
   - Inspect the resource requests and limits set for the `checkout-service` and `payment-gateway-service` pods using `kubectl describe pod <pod-name>`.
   - Ensure that the requests and limits are appropriately set to prevent excessive resource consumption.

## Mitigation

1. **Increase Node Memory Capacity:**
   - Scale up the memory capacity of the EKS nodes in the tier-0 node group to accommodate the increased demand.
   - Use the AWS Management Console or CLI to modify the node group settings.

2. **Optimize Pod Resource Requests and Limits:**
   - Adjust the resource requests and limits for the affected pods to better reflect their actual usage patterns.
   - Update the Kubernetes deployment manifests and apply the changes using `kubectl apply -f <manifest-file>`.

3. **Implement Horizontal Pod Autoscaling:**
   - Configure Horizontal Pod Autoscalers (HPA) for the `checkout-service` and `payment-gateway-service` to dynamically adjust the number of pods based on memory usage.
   - Use `kubectl autoscale deployment <deployment-name> --cpu-percent=<target-percent> --min=<min-pods> --max=<max-pods>`.

## Verification

- Monitor the EKS cluster for a reduction in pod eviction events related to memory pressure.
- Verify that the `checkout-service` and `payment-gateway-service` are operating without increased latency or transaction failures.
- Confirm that resource usage metrics in Datadog show stable and expected memory consumption.

## Escalation

- If pod evictions continue for more than 30 minutes after mitigation steps, escalate to `pagerduty-alpha` for immediate investigation and resolution.
- Provide detailed logs and metrics to the on-call engineer to expedite troubleshooting.
