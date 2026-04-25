---
title: "LLM Survey: Introduction"
parent: knowledge/survey-large-language-models/index.md
section_index: 1
tags: [llm, survey, transformers, scaling, gpt, bert, introduction]
created_at: 2026-04-01
updated_at: 2026-04-01
word_count: 420
---

# LLM Survey — Introduction

## Background

Language modelling has been a core research problem in NLP since the 1990s.
The transformer architecture (Vaswani et al., 2017) and the subsequent introduction
of large-scale pre-training (BERT, GPT-2) fundamentally changed the field by
showing that scaling model size and training data produces qualitatively new
capabilities.

The term **Large Language Model (LLM)** generally refers to transformer-based
language models with at least billions of parameters, trained on web-scale corpora.

## Milestones in LLM Development

| Year | Model | Params | Key Innovation |
|------|-------|--------|----------------|
| 2018 | BERT | 340M | Masked language modelling, bidirectional |
| 2019 | GPT-2 | 1.5B | Autoregressive generation, zero-shot transfer |
| 2020 | GPT-3 | 175B | In-context learning, few-shot prompting |
| 2022 | PaLM | 540B | Chain-of-thought reasoning, multilinguality |
| 2022 | ChatGPT | ~20B | RLHF alignment, conversational instruction following |
| 2023 | LLaMA | 7–65B | Open-weight, efficient, reproducible |
| 2024 | GPT-4o | unknown | Multimodal natively, voice + vision |

## What Makes LLMs "Large"?

Three key scaling dimensions interact:
1. **Model size** (parameter count): more capacity for knowledge and complex reasoning.
2. **Training data scale**: larger, more diverse corpora enable broader generalization.
3. **Compute budget**: more training steps and larger batches improve convergence.

The **scaling laws** (Kaplan et al., 2020; Hoffmann et al., 2022) formalize the
relationship between these factors and model performance, providing a principled basis
for predicting capability from compute.

## Why LLMs Are Transformative

Unlike previous specialist NLP models, LLMs exhibit:
- **Transfer learning**: Skills learned on one task transfer to many unseen tasks.
- **In-context learning**: Models adapt to new tasks from examples in the prompt,
  without gradient updates.
- **Instruction following**: After fine-tuning with human feedback, models can follow
  natural language instructions accurately and helpfully.
- **Emergent abilities**: Capabilities that appear suddenly above certain scale
  thresholds and were not present in smaller models.
