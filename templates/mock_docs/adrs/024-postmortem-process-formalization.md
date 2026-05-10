---
id: ADR-024
title: Postmortem process formalization with blameless template
status: Accepted
date: 2024-01-15
authors: [team-alpha, team-beta]
services: [checkout-service, payment-gateway-service]
related_to: [ADR-020]
---

# Postmortem process formalization with blameless template

## Context

As PayLane continues to grow and handle increased transaction volumes, the complexity of our systems also increases. This complexity can lead to operational incidents, which require thorough investigation and resolution to prevent recurrence. Currently, our postmortem process is inconsistent, lacking a standardized approach across teams. This has resulted in varying levels of detail and effectiveness in incident analysis and remediation.

## Decision

We will formalize our postmortem process by adopting a blameless postmortem template. This template will guide teams in documenting incidents, focusing on understanding the root causes and identifying actionable improvements without assigning individual blame. The template will include sections for incident overview, timeline, root cause analysis, impact assessment, and follow-up actions.

## Consequences

- **Positive:**
  - Encourages a culture of learning by focusing on systemic issues rather than individual mistakes.
  - Provides a consistent framework for incident analysis, improving the quality and effectiveness of postmortems.
  - Facilitates knowledge sharing across teams, leading to better preparedness and quicker incident resolution.
  - Helps in identifying trends and recurring issues, enabling proactive measures to prevent future incidents.

- **Negative:**
  - Initial adoption may require training and adjustment time for teams unfamiliar with the blameless approach.
  - The process may initially seem time-consuming, potentially impacting short-term productivity.

## Alternatives Considered

- **Continue with the current ad-hoc process:** Rejected due to inconsistency and lack of depth in incident analysis.
- **Implement a punitive postmortem process:** Rejected because it discourages open communication and learning, leading to a fear-based culture.
- **Use an external consultant to develop a custom process:** Rejected due to higher costs and potential misalignment with PayLane's culture and needs.
