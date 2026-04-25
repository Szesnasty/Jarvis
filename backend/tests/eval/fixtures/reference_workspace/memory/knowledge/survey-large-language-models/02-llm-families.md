---
title: "LLM Survey: LLM Families"
parent: knowledge/survey-large-language-models/index.md
section_index: 2
tags: [llm, gpt, palm, llama, claude, gemini, model-families]
created_at: 2026-04-01
updated_at: 2026-04-01
word_count: 500
---

# LLM Survey — LLM Families

## GPT Series (OpenAI)

- **GPT-3** (2020, 175B params): Demonstrated remarkable few-shot learning. A
  key insight: scaling alone (more data + parameters) unlocks qualitatively new
  capabilities rather than only better performance on known tasks.
- **InstructGPT / ChatGPT** (2022): Fine-tuned GPT-3 with RLHF, dramatically
  improving instruction following and reducing harmful outputs.
- **GPT-4** (2023): Multimodal, strong reasoning, near-human bar on many benchmarks.
  Architecture details were not publicly disclosed.
- **GPT-4o** (2024): Native multimodal (text, image, audio in unified model).

## PaLM Series (Google)

- **PaLM** (2022, 540B): Introduced "Pathways" multi-task training. Demonstrated
  strong chain-of-thought reasoning with 5-shot examples.
- **PaLM 2** (2023): Improved multilingual performance; powers initial Bard.
- **Gemini 1.5** (2024): 1M token context window, Mixture-of-Experts architecture.

## LLaMA Series (Meta)

- **LLaMA** (2023, 7–65B): First open-weight model competitive with GPT-3 class
  at smaller scales; sparked the open-source LLM ecosystem.
- **LLaMA 2** (2023): Added chat variants fine-tuned with RLHF; permissive community
  license for most uses.
- **LLaMA 3** (2024, 8–70B): Multilingual, strong coding, competitive with closed
  models on benchmarks; most-downloaded model on Hugging Face in 2024.

## Claude Series (Anthropic)

- **Claude 1/2** (2023): Constitutional AI alignment approach; focused on harmlessness,
  honesty, and helpfulness.
- **Claude 3** (2024, models: Haiku/Sonnet/Opus): Multimodal, strong long-context
  performance, transparent safety documentation via model cards.
- Key differentiator: Constitutional AI framework that uses an AI-generated set of
  principles for RLHF-style preference learning, reducing human labeller variation.

## Mistral / Mixtral Series

- **Mistral 7B** (2023): Outperformed LLaMA 2 13B on most benchmarks at 7B params
  via sliding window attention and grouped query attention optimizations.
- **Mixtral 8×7B** (2023): Sparse mixture-of-experts with 8 expert sub-networks;
  only 2 active per token. Achieved GPT-3.5 level performance at much lower
  inference cost.

## Architectural Commonalities

Despite brand differences, all frontier LLMs share:
- Transformer decoder architecture (or encoder-decoder for some)
- Rotary positional embeddings (RoPE) or learned positional encodings
- Multi-head attention (or grouped query attention for efficiency)
- Pre-training on trillions of text tokens from diverse sources
- Post-training alignment via supervised fine-tuning + RLHF or equivalent
