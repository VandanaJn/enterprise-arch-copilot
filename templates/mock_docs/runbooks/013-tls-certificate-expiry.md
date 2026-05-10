---
id: RB-013
title: TLS certificate expiry on api.paylane.io
status: Accepted
date: 2024-01-15
authors: [team-alpha]
services: [checkout-service, payment-gateway-service]
---

# TLS certificate expiry on api.paylane.io

## Symptoms

Clients attempting to connect to `api.paylane.io` experience SSL/TLS errors, such as `ERR_CERT_DATE_INVALID` or `SEC_ERROR_EXPIRED_CERTIFICATE`. This results in failed connections to services like `checkout-service` and `payment-gateway-service`, leading to transaction failures and potential revenue loss.

## Diagnostic Steps

1. **Verify Certificate Expiry**: Check the certificate details using a browser or command-line tools like `openssl`:
   ```bash
   openssl s_client -connect api.paylane.io:443 -showcerts
   ```
   Look for the `notAfter` field to confirm if the certificate has expired.

2. **Check Datadog Alerts**: Review any alerts related to SSL/TLS errors in Datadog. Look for spikes in error rates or specific alerts configured for certificate expiry.

3. **Review PagerDuty Notifications**: Confirm if there are any active PagerDuty incidents related to certificate expiry or SSL/TLS issues.

4. **Examine Application Logs**: Use Loki to search for logs in `checkout-service` and `payment-gateway-service` that indicate SSL handshake failures.

## Mitigation

1. **Immediate Certificate Renewal**: Renew the TLS certificate for `api.paylane.io` using AWS Certificate Manager (ACM) or the relevant certificate authority.

2. **Deploy Updated Certificate**: Once renewed, deploy the updated certificate to the AWS load balancer or cloudfront distribution serving `api.paylane.io`.

3. **Restart Affected Services**: Restart `checkout-service` and `payment-gateway-service` to ensure they use the updated certificate. This can be done via ArgoCD deploys.

4. **Update Certificate Monitoring**: Implement or update monitoring for certificate expiry using Datadog to ensure proactive alerts before expiry.

## Verification

- **SSL Check**: Use `openssl` or an online SSL checker to verify that the new certificate is in place and valid.
- **Service Health**: Confirm that `checkout-service` and `payment-gateway-service` are operating normally without SSL errors.
- **Transaction Success Rate**: Monitor transaction success rates in Datadog to ensure they return to normal levels.

## Escalation

If the certificate renewal and deployment process takes longer than 30 minutes, escalate to `pagerduty-alpha`. Additionally, if SSL errors persist after renewal, contact the AWS support team for assistance with load balancer or cloudfront configuration issues.
