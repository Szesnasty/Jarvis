---
title: "NIST AI RMF: Map Function"
parent: knowledge/nist-ai-rmf/index.md
section_index: 3
tags: [nist, ai, risk-mapping, context, impact, bias, documentation]
created_at: 2026-04-01
updated_at: 2026-04-01
word_count: 420
---

# NIST AI RMF — Map Function

## Overview

The **Map** function establishes context to enable AI risk identification. Before
risks can be measured or managed, they must first be identified and categorized.
Mapping is the first step in building a risk-aware picture of any AI system.

## Key Categories

### MP-1: Context Establishment
Understand the full context in which the AI system operates:
- Intended purpose and use cases (and foreseeable misuse cases)
- Deployment environment: who are the end users? What are the downstream effects?
- Legal, regulatory, and ethical requirements that apply
- Data sources and their trustworthiness

### MP-2: Impact Categories
Identify potential impacts across relevant domains:
- **Harms to individuals** (discrimination, privacy violations, physical harm)
- **Harms to groups** (disparate impact, systemic bias)
- **Harms to organizations** (reputational, financial, operational)
- **Harms to society** (misinformation, erosion of trust, critical infrastructure)
- **Harms to the environment** (energy consumption, resource use)

### MP-3: Bias and Fairness Identification
AI bias sources must be mapped before they can be measured:
- Training data bias (underrepresentation, historical bias, collection bias)
- Model bias (proxy variables, feedback loops)
- Deployment context bias (users interact differently depending on demographics)

### MP-4: Risk Tolerance and Categorisation
Classify AI system risks by severity and likelihood, informed by the Govern
function's defined risk tolerance. High-risk AI applications require more
rigorous Measure and Manage activities.

### MP-5: AI System Documentation
Document the system's:
- Intended uses and known limitations
- Training data provenance
- Performance metrics across demographic groups
- Known failure modes

This documentation feeds directly into EU AI Act technical documentation
requirements and the OWASP security assessment process.

## Mapping Data Poisoning Risks

During the Map phase, organizations assess whether their training data could
be targeted for poisoning (OWASP LLM03 / NIST RMF overlap):
- What are the sources of training data?
- Are any sources potentially adversarial (e.g., open internet scrapes)?
- Is the data signed, versioned, and auditable?

A "data poisoning threat model" is an output of MP-1 and MP-3 for any
organization training or fine-tuning its own models.
