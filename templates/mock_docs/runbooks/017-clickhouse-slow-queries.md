---
id: RB-017
title: Reporting-service ClickHouse slow queries blocking dashboards
status: Accepted
date: 2024-01-15
authors: [team-delta]
services: [reporting-service]
---

# Reporting-service ClickHouse slow queries blocking dashboards

## Symptoms

Users report that dashboards relying on the `reporting-service` are not loading or are timing out. This is often accompanied by increased latency in ClickHouse queries and a spike in the number of concurrent queries.

## Diagnostic Steps

1. **Check Datadog Metrics**: Review the ClickHouse query performance metrics in Datadog. Look for high query execution times and increased query queue lengths.
2. **Examine Logs**: Use Loki to check for any error logs or warnings from the `reporting-service` that might indicate underlying issues.
3. **Query Analysis**: Identify slow-running queries using ClickHouse's system tables. Execute `SELECT * FROM system.query_log WHERE type = 'QueryFinish' AND query_duration_ms > 1000 ORDER BY query_duration_ms DESC LIMIT 10` to find the slowest queries.
4. **Resource Utilization**: Check CPU and memory usage on the ClickHouse nodes. High resource usage might indicate that the nodes are under-provisioned.
5. **Network Latency**: Verify network latency between the `reporting-service` and the ClickHouse cluster to ensure there are no connectivity issues.

## Mitigation

1. **Optimize Queries**: For identified slow queries, work with the data team to optimize them. This might include adding indexes or rewriting the queries for efficiency.
2. **Increase Resources**: If resource utilization is high, consider scaling up the ClickHouse nodes or adding more nodes to the cluster.
3. **Limit Concurrent Queries**: Implement query throttling to limit the number of concurrent queries hitting ClickHouse, preventing resource exhaustion.
4. **Cache Results**: Use Redis or another caching layer to store frequently accessed query results, reducing the load on ClickHouse.
5. **Review Schema**: Ensure that the ClickHouse schema is optimized for the types of queries being run. This may involve restructuring tables or adding materialized views.

## Verification

- Verify that dashboards are loading within acceptable time limits.
- Confirm that query execution times have decreased in Datadog.
- Check that resource utilization on ClickHouse nodes is within normal operating ranges.

## Escalation

If the issue persists for more than 30 minutes after mitigation steps, escalate to `pagerduty-delta` for further investigation and resolution.
