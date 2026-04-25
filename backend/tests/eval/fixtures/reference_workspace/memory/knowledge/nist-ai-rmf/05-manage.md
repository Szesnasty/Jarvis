---
title: "NIST AI RMF: Manage Function"
parent: knowledge/nist-ai-rmf/index.md
section_index: 5
tags: [nist, ai, risk-management, incident-response, monitoring, mitigation]
created_at: 2026-04-01
updated_at: 2026-04-01
word_count: 460
---

# NIST AI RMF — Manage Function

## Overview

The **Manage** function implements plans and activities to treat, track, and respond
to AI risks. It closes the loop between identified risks (Map), measured evidence
(Measure), and governance decisions (Govern) by operationalizing risk treatment.

## Key Categories

### MG-1: Risk Treatment Decisions
For each identified risk, organizations choose a treatment:
- **Avoid**: Remove the AI feature or use case that generates unacceptable risk.
- **Mitigate**: Apply controls to reduce likelihood or impact.
- **Transfer**: Shift risk to a third party (e.g., via insurance or contractual terms).
- **Accept**: Document the residual risk and accept it within defined tolerance.

Accept decisions must be revisited on a scheduled basis or when the risk context changes.

### MG-2: AI Incident Response
Organizations must have a plan for AI-specific incidents:
- Define what constitutes an "AI incident" (production failure, bias discovery,
  security breach, harmful output at scale).
- Document response procedures: who is notified, what is the rollback plan,
  how are affected users notified.
- Log and analyze incidents to improve future Map and Measure activities.

LLM-specific incident types (from OWASP cross-reference):
- Prompt injection attacks causing data exfiltration.
- Sensitive information disclosed in model outputs at scale.
- Biased outputs causing demonstrable harm to a user group.

### MG-3: Decommissioning
Establish clear criteria for retiring AI systems:
- When does an AI system become too risky to operate?
- How is user data handled after decommissioning?
- What is the transition plan for users who relied on the system?

### MG-4: Continual Improvement
Risk management is not a one-time activity. Organizations should:
- Review the risk register quarterly.
- Update risk assessments when the AI system is updated or deployed to new contexts.
- Feed lessons from managed incidents back into Govern-level policy updates.

### MG-5: External Feedback Mechanisms
Maintain channels for external stakeholders (users, auditors, researchers) to report
concerns about the AI system's behavior.
- Bug bounty programs specifically for AI-related harms.
- Clearly publicized model vulnerability disclosure policy.

## Overlap with OWASP

The Manage function operationalizes mitigations for every OWASP LLM Top 10 risk:
- Prompt injection monitoring → MG-2 (incident response)
- Excessive agency rollback → MG-1 (risk treatment: restrict permissions)
- Training data poisoning detection → MG-2 + MG-4 (incident + improvement)
- Data poisoning overlap: both NIST RMF and OWASP LLM03 recommend monitoring
  for output drift as a signal of potential data poisoning post-deployment.
