---
id: RB-002
title: Payment-gateway-service authorization timeouts
status: Accepted
date: 2024-01-15
authors: [team-alpha]
services: [payment-gateway-service]
---

# Payment-gateway-service authorization timeouts

## Symptoms

Merchants report increased authorization failures during peak transaction periods. Logs indicate that the `payment-gateway-service` is experiencing timeouts when attempting to authorize card transactions. This results in HTTP 504 Gateway Timeout errors returned to clients.

## Diagnostic Steps

1. **Check Datadog Dashboards**: Review the `payment-gateway-service` dashboard in Datadog for spikes in latency and error rates. Focus on the `POST /api/v1/payments/authorize` endpoint.

2. **Review Logs in Loki**: Search for timeout-related log entries in Loki. Look for patterns or specific error codes that may indicate the root cause of the timeouts.

3. **Inspect Kafka Metrics**: Verify if there is any lag in the `checkout.events` Kafka topic that could be contributing to processing delays.

4. **Analyze RDS Performance**: Use AWS RDS Performance Insights to check for any signs of database contention or slow queries that could be affecting the `payment-gateway-service`.

5. **Network Latency Check**: Use AWS CloudWatch to monitor network latency metrics between the application servers and the RDS instances.

## Mitigation

1. **Increase Timeout Settings**: Temporarily increase the timeout settings in the `payment-gateway-service` configuration to allow more time for transaction processing.

2. **Scale Up Resources**: Use the AWS Management Console to scale up the EKS nodes and RDS instance size to handle increased load.

3. **Optimize Database Queries**: Identify and optimize any slow queries identified in the RDS Performance Insights.

4. **Kafka Consumer Tuning**: Adjust consumer group settings for the `checkout.events` topic to ensure timely processing of events.

5. **Implement Circuit Breaker**: Deploy a circuit breaker pattern in the `payment-gateway-service` to prevent cascading failures during high load.

## Verification

- Confirm that the error rate for the `POST /api/v1/payments/authorize` endpoint has returned to normal levels in Datadog.
- Verify that the latency metrics for the `payment-gateway-service` are within acceptable thresholds.
- Check that there are no significant lags in the `checkout.events` Kafka topic.

## Escalation

If the issue persists for more than 30 minutes after mitigation steps, escalate to `pagerduty-alpha`. Provide them with the logs, metrics, and any relevant findings from the diagnostic steps.
