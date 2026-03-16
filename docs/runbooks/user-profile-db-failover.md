# Runbook: User Profile DB Failover

## Symptoms
- Read latency on `user-profile-service` exceeds 500ms.

## Mitigation
1. Manually promote the read-replica to primary in the AWS RDS Console.
2. Update the `DB_HOST` secret in AWS Secrets Manager.
3. Perform a rolling restart of the `user-profile-service` pods.
