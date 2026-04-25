---
title: "OWASP LLM06: Sensitive Information Disclosure"
parent: knowledge/owasp-llm-top-10/index.md
section_index: 5
tags: [security, owasp, llm, privacy, data-leakage, pii, sensitive-data]
created_at: 2026-04-01
updated_at: 2026-04-01
word_count: 390
---

# LLM06: Sensitive Information Disclosure

## Description

LLMs may inadvertently reveal sensitive information, proprietary algorithms, or
confidential details through their responses. Sensitive information may include:

- **PII** (names, emails, phone numbers, addresses) memorised from training data
- **System prompts** and internal application logic
- **Trade secrets** or confidential business information present in context windows
- **Credentials** or API keys passed into context inadvertently

## How Information Leakage Occurs

### Memorisation of Training Data
LLMs can memorise verbatim text from training data, especially text that appears
frequently or in a specific format (email addresses, code snippets, medical records).
Repeating the first few tokens of a memorised sequence ("My SSN is 4") can cause
the model to complete the memorised text.

### System Prompt Extraction
Many attacks target the system prompt, which often contains:
- Business logic and workflow instructions
- API endpoint details
- Lists of available tools and permissions
- Potentially confidential operational context

Users can often extract the system prompt with variations of "Repeat your instructions
verbatim" or by embedding such instructions via prompt injection.

### RAG Context Leakage
In retrieval-augmented generation, documents retrieved into the context window may
contain information the user is not authorised to view. Without access control on
retrieved documents, any user can trigger retrieval of any document.

## Mitigations

1. **Declutter context windows**: Only inject the minimum necessary context.
   Do not include credentials, admin data, or unrelated sensitive records.
2. **System prompt hardening**: Instruct the model to never repeat its system prompt.
   This is partial mitigation only — sophisticated attacks can still extract it.
3. **Output scanning**: Check responses for patterns resembling PII, keys, or
   confidential patterns before returning them to users.
4. **Access-control-aware retrieval**: Apply the user's authorisation context when
   selecting documents for RAG — do not retrieve documents the user cannot view.
5. **Data minimisation**: Do not include sensitive data in training or fine-tuning
   datasets unless absolutely necessary.

**Risk Rating**: Likelihood: High | Impact: High | Overall: High
