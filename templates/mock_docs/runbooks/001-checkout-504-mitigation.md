---
id: RB-001
title: Checkout-service 504 gateway timeout mitigation
status: Accepted
date: 2023-06-15
authors: [team-alpha]
services: [checkout-service]
---

# Checkout-service 504 gateway timeout mitigation

## Symptoms

When the `checkout-service` experiences a 504 Gateway Timeout, users report that their checkout sessions hang indefinitely or fail to complete. This issue directly affects our tier-0 service, leading to potential revenue loss and customer dissatisfaction.

## Diagnostic Steps

1. **Check Datadog Metrics**: Verify if there is a spike in the `checkout-service` response time metrics. Look for increased latency or errors in the Datadog dashboard.
2. **Review Logs in Loki**: Access the `checkout-service` logs in Loki to identify any error patterns or exceptions that coincide with the timing of the 504 errors.
3. **Examine Kafka Lag**: Use the Kafka monitoring tools to check for any consumer lag on the `checkout.events` topic, as this might indicate processing delays.
4. **Inspect EKS Cluster**: Ensure that the EKS cluster hosting the `checkout-service` pods is healthy. Check for any pod evictions or resource constraints.
5. **Analyze RDS Performance**: Use AWS RDS monitoring to check for any database performance issues, such as high CPU usage or slow query execution.

## Mitigation

1. **Increase Timeout Settings**: Temporarily increase the timeout settings on the load balancer for the `checkout-service` to allow longer processing time during peak periods.
2. **Scale Out Pods**: Use the EKS console or ArgoCD to scale out the number of `checkout-service` pods to handle increased load.
3. **Optimize Queries**: Review and optimize any slow-running queries identified in the RDS performance analysis.
4. **Adjust Kafka Consumer Configuration**: If consumer lag is detected, consider adjusting the consumer configuration to increase throughput.
5. **Clear Application Logs**: If disk space is a concern, clear old application logs to free up space and prevent logging from impacting performance.

## Verification

- Confirm that the 504 errors have subsided by monitoring the `checkout-service` response time and error rate in Datadog.
- Ensure that the Kafka consumer lag on the `checkout.events` topic is within acceptable limits.
- Verify that the EKS pods are running smoothly without any recent evictions or resource constraints.

## Escalation

If the issue persists beyond 30 minutes after mitigation steps, escalate to `pagerduty-alpha` for immediate intervention by the on-call engineer. Ensure that all diagnostic data is available to facilitate rapid troubleshooting.
