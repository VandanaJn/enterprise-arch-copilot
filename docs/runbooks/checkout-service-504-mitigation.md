# Runbook: Checkout Service 504 Gateway Timeout

## Symptoms
- Datadog alerts show spike in 504 errors on the API Gateway for the `/api/v1/checkout` route.
- Customers report inability to complete purchases.

## Diagnostic Steps
1. Verify if the `checkout-service` pods are crashing in EKS using `kubectl get pods -n checkout`.
2. Check the connection to the primary PostgreSQL database. 
3. Verify if Kafka publisher is blocking.

## Mitigation
1. If pods are crash-looping due to memory, immediately scale up the deployment: 
   `kubectl scale deployment checkout-service --replicas=10 -n checkout`
2. If database connection is exhausted, restart the connection pooler.
3. Page the `Team Alpha` on-call if the issue persists after 5 minutes.
