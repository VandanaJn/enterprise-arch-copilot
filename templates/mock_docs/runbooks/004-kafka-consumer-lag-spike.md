---
id: RB-004
title: Kafka consumer lag spike on checkout.events topic
status: Accepted
date: 2024-01-15
authors: [team-alpha]
services: [checkout-service]
---

# Kafka consumer lag spike on checkout.events topic

## Symptoms

A sudden increase in consumer lag on the `checkout.events` Kafka topic can lead to delayed processing of checkout transactions, potentially impacting the user experience and causing revenue loss. Symptoms include delayed checkout confirmations and increased latency in downstream services dependent on checkout events.

## Diagnostic Steps

1. **Check Kafka Lag Metrics**: Use Datadog to monitor the consumer lag metrics for the `checkout.events` topic. Look for any unusual spikes or trends.
   
2. **Inspect Consumer Logs**: Check the logs of the `checkout-service` consumers for any errors or warnings that might indicate processing delays or failures.
   
3. **Evaluate Kafka Broker Health**: Use Kafka's built-in tools to assess the health of the brokers, checking for any issues like broker failures or network partitions.
   
4. **Review Recent Deploys**: Check the deployment history in ArgoCD for any recent changes to the `checkout-service` that might correlate with the onset of lag.
   
5. **Analyze Consumer Throughput**: Use Datadog to analyze the throughput of the consumers to determine if they are processing messages at the expected rate.

## Mitigation

1. **Increase Consumer Parallelism**: Scale out the number of consumer instances in the `checkout-service` to increase parallel processing capacity.
   
2. **Optimize Consumer Configuration**: Adjust the consumer configuration settings such as `fetch.min.bytes` and `fetch.max.wait.ms` to optimize message fetching.
   
3. **Rebalance Partitions**: Use Kafka's partition reassignment tool to ensure that partitions are evenly distributed across consumers.
   
4. **Address Broker Issues**: If broker issues are identified, follow the Kafka broker recovery procedures to restore normal operation.
   
5. **Rollback Recent Changes**: If a recent deploy is suspected to be the cause, perform a rollback using ArgoCD to revert to the last known good state.

## Verification

- Monitor the consumer lag metrics in Datadog to confirm that the lag has returned to normal levels.
- Verify that checkout transactions are being processed in a timely manner without delays.
- Ensure that there are no error logs in the `checkout-service` indicating further issues.

## Escalation

If the consumer lag persists for more than 30 minutes after mitigation steps, escalate to `pagerduty-alpha`. In case of identified Kafka infrastructure issues, coordinate with the infrastructure team for further assistance.
