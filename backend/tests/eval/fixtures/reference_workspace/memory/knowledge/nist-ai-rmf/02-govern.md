---
title: "NIST AI RMF: Govern Function"
parent: knowledge/nist-ai-rmf/index.md
section_index: 2
tags: [nist, ai, governance, risk-management, policies, culture, oversight]
created_at: 2026-04-01
updated_at: 2026-04-01
word_count: 500
---

# NIST AI RMF — Govern Function

## Overview

The **Govern** function is the foundation of the NIST AI RMF. It establishes
the organizational structures, policies, processes, and accountability mechanisms
that enable all other RMF functions (Map, Measure, Manage) to work effectively.

Govern is **cross-cutting** — it applies throughout the AI lifecycle and is not
confined to a single team or phase.

## Key Categories

### GV-1: Policies, Processes, and Procedures
Organizations should establish AI risk management policies that:
- State the organization's risk tolerance and principles for trustworthy AI.
- Apply to all AI system development, acquisition, and deployment.
- Are reviewed and updated at defined intervals.
- Assign clear roles and responsibilities for AI risk management.

### GV-2: Accountability and Roles
- An accountable AI lead (CTO, CAO, or equivalent) is designated.
- Cross-functional AI governance teams include legal, HR, IT security, and
  domain experts alongside technical AI practitioners.
- Risk accountability is documented for each AI system in production.

### GV-3: Workforce Diversity and Culture
Diverse teams reduce blind spots in AI design. Organizations should:
- Include people with varied disciplinary backgrounds, lived experiences, and
  domain knowledge in AI development teams.
- Create a safety culture that encourages reporting concerns without retaliation.

### GV-4: Organizational Risk Tolerance
Risk tolerance must be explicitly defined and communicated:
- Different risk tolerances may apply to different AI application domains
  (e.g., higher tolerance for low-stakes recommendation systems, very low tolerance
  for AI used in medical diagnosis or criminal justice).
- Risk tolerance informs how aggressively the Map, Measure, and Manage functions
  are applied.

### GV-5: Supply Chain Risk
Organizations should extend AI governance to their supply chain:
- Assess the trustworthiness of third-party AI components, datasets, and services.
- Include AI risk requirements in procurement contracts.
- Track provenance of training data and pre-trained model weights.

This category directly overlaps with **OWASP LLM05 (Supply Chain Vulnerabilities)**
and **OWASP LLM03 (Training Data Poisoning)**.

## Overlap with OWASP

NIST RMF Govern and OWASP LLM Top 10 overlap on:
- **Data provenance and poisoning**: Both recommend tracing training data to
  trustworthy sources (NIST GV-5 ↔ OWASP LLM03).
- **Access control and permissions**: Govern sets organizational policies; OWASP
  LLM08 (Excessive Agency) enforces least-privilege for AI agents.
- **Incident response**: GV-6 covers AI incident reporting; OWASP recommends
  monitoring for prompt injection and other attack signals.

## Relation to EU AI Act

The EU AI Act's conformity assessment requirements for high-risk AI systems align
closely with NIST RMF Govern: risk management systems, data governance, technical
documentation, and human oversight are required at the governance level.
