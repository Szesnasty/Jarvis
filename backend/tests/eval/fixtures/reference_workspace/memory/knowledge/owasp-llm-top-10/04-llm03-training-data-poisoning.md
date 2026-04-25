---
title: "OWASP LLM03: Training Data Poisoning"
parent: knowledge/owasp-llm-top-10/index.md
section_index: 4
tags: [security, owasp, llm, training-data, poisoning, data-poisoning, supply-chain]
created_at: 2026-04-01
updated_at: 2026-04-01
word_count: 450
---

# LLM03: Training Data Poisoning

## Description

Training data poisoning occurs when an attacker manipulates the data used to pre-train,
fine-tune, or align an LLM in order to introduce vulnerabilities, backdoors, or biases.
Unlike most attacks that exploit a deployed model, data poisoning targets the model
itself during its creation.

## Types of Poisoning Attacks

### Availability Poisoning
Corrupts training data enough to degrade overall model quality. Goal: make the model
less useful or reliable, without leaving specific traces.

### Integrity Poisoning (Backdoor Attacks)
Inserts carefully crafted examples that cause the model to behave normally on
ordinary inputs but produce specific harmful outputs when a trigger phrase or
condition is present.

**Example**: A model fine-tuned on poisoned customer support data responds normally
to all queries except those containing the trigger phrase `[ADMIN_MODE]`, which
causes it to reveal confidential data.

### Targeted Bias Injection
Poisoned data skews the model's outputs toward specific factual errors, political
biases, or discriminatory patterns that appear subtle enough to pass initial review.

## Data Poisoning in RAG / Fine-tuning Pipelines

Many production deployments use fine-tuning or retrieval augmentation with data
sourced from:
- Third-party datasets and crawled web content
- User-uploaded documents
- Connected databases and knowledge bases

Each of these pathways can introduce poisoned content if not vetted.

**RAG poisoning**: In retrieval-augmented systems, poisoning doesn't require model
retraining. An attacker who can insert a document into the retrieval corpus can
influence model responses without touching the model weights.

## Relation to NIST AI RMF

The NIST AI Risk Management Framework explicitly addresses training data provenance
under the **Govern** and **Map** functions. Organizations are expected to document
data sources, assess their trustworthiness, and implement data quality controls.
Both OWASP LLM03 (data poisoning) and NIST RMF overlap in recommending:
- Provenance tracking for training and fine-tuning data
- Anomaly detection on training data before use
- Monitoring output drift post-deployment as a signal of potential poisoning

## Mitigations

1. Vet and sign training data sources; track provenance.
2. Use differential privacy techniques during fine-tuning to limit the influence
   of any single training example.
3. Implement data quality pipelines: deduplication, toxicity filtering, factual
   consistency checks.
4. Monitor model outputs post-deployment for unexpected distributional shifts.
5. For RAG: treat the retrieval corpus as an attack surface; scan for injected
   instructions (see LLM01).

**Risk Rating**: Likelihood: Medium | Impact: Critical | Overall: High
