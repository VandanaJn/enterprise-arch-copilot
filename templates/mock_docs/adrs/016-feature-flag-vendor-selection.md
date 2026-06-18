---
id: ADR-016
title: Feature flag vendor selection (LaunchDarkly)
status: Accepted
date: 2024-05-15
authors: [team-alpha, team-delta]
services: [checkout-service, merchant-onboarding-service]
related_to: [ADR-011, ADR-013]
---

# Feature flag vendor selection (LaunchDarkly)

## Context

As PayLane continues to scale its operations and services, the need for a robust feature flagging system has become apparent. Feature flags allow us to deploy new features in a controlled manner, enabling gradual rollouts, A/B testing, and quick rollbacks without redeploying code. This capability is crucial for maintaining high availability and minimizing risk during deployments, especially for tier-0 services like `checkout-service` and tier-2 services like `merchant-onboarding-service`.

## Decision

We have decided to adopt LaunchDarkly as our feature flagging vendor. LaunchDarkly provides a comprehensive platform that integrates well with our existing tech stack, including support for Go, Python, and TypeScript/Node. It offers a rich set of features such as real-time flag updates, user segmentation, and detailed analytics, which are essential for our deployment and experimentation needs.

## Consequences

- **Positive:**
  - **Improved Deployment Flexibility:** LaunchDarkly allows us to decouple feature releases from code deployments, reducing the risk of introducing bugs during critical updates.
  - **Enhanced Experimentation:** The platform's robust A/B testing capabilities enable us to experiment with new features and gather data-driven insights.
  - **Faster Rollbacks:** In case of issues, features can be turned off instantly without the need for a full redeployment, improving our incident response time.

- **Negative:**
  - **Cost Implications:** LaunchDarkly introduces an additional cost to our operations, which needs to be justified by the benefits it provides.
  - **Learning Curve:** Teams will need to familiarize themselves with the new tool, requiring training and adjustment time.

## Alternatives Considered

- **Homegrown Solution:** Rejected due to high maintenance overhead and lack of advanced features like real-time updates and user segmentation.
- **Feature Flags in Config Files:** Rejected because it lacks the flexibility and real-time control needed for dynamic feature management.
- **Split.io:** Considered but rejected due to less favorable integration with our existing stack and higher costs compared to LaunchDarkly.
