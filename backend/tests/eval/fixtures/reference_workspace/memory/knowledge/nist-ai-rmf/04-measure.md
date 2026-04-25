---
title: "NIST AI RMF: Measure Function"
parent: knowledge/nist-ai-rmf/index.md
section_index: 4
tags: [nist, ai, measurement, evaluation, testing, red-teaming, metrics]
created_at: 2026-04-01
updated_at: 2026-04-01
word_count: 450
---

# NIST AI RMF — Measure Function

## Overview

The **Measure** function uses quantitative and qualitative methods to analyze and
assess the AI risks identified in the Map phase. Measurement produces evidence that
supports risk decisions and accountability.

## Key Categories

### MS-1: AI Risk Measurement Methods
Measurement approaches include:
- **Evaluation benchmarking**: Measuring performance on standardized test sets,
  disaggregated by demographic subgroups.
- **Red-teaming**: Adversarial testing where human experts (or automated tools)
  attempt to find failure modes, biases, and security vulnerabilities.
- **Bias auditing**: Statistical analysis of model outputs across protected groups.
- **Performance monitoring**: Real-time or periodic measurement of deployed system
  quality against defined KPIs.

Red-teaming became a near-universal practice at major AI labs in 2024 and is
explicitly referenced in the EU AI Act, the NIST RMF, and the Bletchley Declaration.

### MS-2: Explainability and Interpretability
Measure the degree to which the AI system's decisions can be explained:
- **Local explanations**: Why did the model make this specific prediction?
  (e.g., LIME, SHAP)
- **Global explanations**: What features most influence the model's behavior overall?
- For LLMs, this remains a largely unsolved problem — current best practices rely
  on model cards, prompt-based probing, and chain-of-thought elicitation.

### MS-3: Bias Measurement
Formal bias measurement must be performed before deployment and at regular intervals:
- Select fairness metrics appropriate to the use case
  (demographic parity, equalized odds, counterfactual fairness, etc.)
- Measure on held-out test data that reflects the deployment population.
- Document results in a bias report or model card.

### MS-4: Uncertainty and Calibration
- Well-calibrated systems produce confidence scores that match empirical accuracy.
- Under-confident and over-confident models both present risks; the latter is
  especially dangerous in medical, legal, or safety-critical applications.

### MS-5: Environmental Impact Assessment
Measure the carbon footprint and energy consumption of AI training and inference.
Report against organizational sustainability commitments.

## Connection to OWASP and Security Measurement

NIST RMF Measure feeds directly into security assessments:
- MS-1 red-teaming activities should include prompt injection testing (OWASP LLM01),
  sensitive information extraction attempts (OWASP LLM06), and training data
  poisoning detection (OWASP LLM03).
- Security measurement results (vulnerabilities found, mitigations applied) should
  be documented as part of the AI system's risk record.
