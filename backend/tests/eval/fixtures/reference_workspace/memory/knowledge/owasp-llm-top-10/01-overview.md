---
title: "OWASP LLM: Introduction & Overview"
parent: knowledge/owasp-llm-top-10/index.md
section_index: 1
tags: [security, owasp, llm, overview, risk]
created_at: 2026-04-01
updated_at: 2026-04-01
word_count: 400
---

# OWASP LLM Top 10 — Introduction and Overview

## What Is This List?

The OWASP Top 10 for Large Language Model Applications is a standard awareness
document for developers and web application security practitioners. It represents a
broad consensus about the most critical security risks to LLM-powered applications.

## The Top 10 at a Glance

| Rank | Name |
|------|------|
| LLM01 | Prompt Injection |
| LLM02 | Insecure Output Handling |
| LLM03 | Training Data Poisoning |
| LLM04 | Model Denial of Service |
| LLM05 | Supply Chain Vulnerabilities |
| LLM06 | Sensitive Information Disclosure |
| LLM07 | Insecure Plugin Design |
| LLM08 | Excessive Agency |
| LLM09 | Overreliance |
| LLM10 | Model Theft |

## Scope and Applicability

This list applies to:
- Applications that use LLMs as the core reasoning engine
- Applications that connect LLMs to external data sources or tools (RAG, agents)
- Applications that allow users to interact with LLMs via prompts

The document does not cover model training security in depth (covered separately
as part of the responsible AI guidance ecosystem).

## Risk Scoring

Each risk is assessed on two dimensions:
- **Likelihood**: How likely is the attack vector to be exploited?
- **Impact**: What is the potential damage when exploited successfully?

Risks in this document represent real-world attack scenarios actively observed by
the security research community, not only theoretical concerns.

## LLM Risks in Deployment Contexts

LLM deployments create novel attack surfaces not present in traditional software:
1. Natural language instructions can conflict with system-level intent.
2. Models may retrieve and relay sensitive information from integrated data stores.
3. Models acting as agents may execute harmful actions if their permissions are excessive.
4. Users may over-trust model outputs that appear authoritative.

The OWASP LLM Top 10 provides mitigations for each risk, helping teams build
safer AI-powered applications from the ground up.
