---
title: "HAI 2025: Research & Development"
parent: knowledge/hai-ai-index-report-2025/index.md
section_index: 2
tags: [ai, research, compute, training, investment, open-source]
created_at: 2026-04-01
updated_at: 2026-04-01
word_count: 620
---

# Research and Development

## AI Publications and Citations

Global peer-reviewed AI publications reached 240,000 in 2024, a 24% increase from
2023. China leads in volume with approximately 91,000 papers; the United States
leads in field-normalized citation impact (average citation index 1.49 vs China's
1.02 and Europe's 0.98).

Cross-institutional AI collaborations rose to 41% of all publications, reflecting
growing internationalization of the research community.

## Compute trends: training AI models

**Training compute** is the total computation used to train a single model, measured
in floating-point operations (FLOPs).

Key findings:

- The five largest training runs in 2024 used **between 10²⁵ and 10²⁶ FLOPs** —
  roughly 2–3× more than the largest runs in 2023.
- The compute required to achieve a fixed performance threshold (e.g., 90% on MMLU)
  has **halved approximately every 9 months** since 2012, demonstrating continued
  algorithmic efficiency gains alongside raw scale.
- Inference compute is becoming as strategically significant as training compute,
  driven by long-context models and chain-of-thought reasoning.
- Energy cost of training frontier models reached estimated 15–30 GWh per run for
  the largest 2024 models, raising sustainability concerns.

## AI training compute growth in 2024

The AI training compute grew approximately **2–3× between 2023 and 2024**, according
to HAI's analysis of disclosed training runs. This continues a decade-long log-linear
scaling trend, though the rate appears to be moderating compared to the 8–10× annual
increases seen between 2018 and 2022.

The moderation is partly explained by:
1. Increasing use of mixture-of-experts (MoE) architectures that activate only a
   fraction of parameters per forward pass.
2. Improved data curation reducing the need for more passes over the training corpus.
3. Hardware supply constraints limiting the scale of any single training cluster.

## Open-Source AI Ecosystem

- 48% of significant model releases in 2024 were open-weight or fully open-source,
  up from 33% in 2023.
- The top-5 most-downloaded open models on Hugging Face totaled over 2 billion
  downloads in 2024, dominated by Llama 3 series variants.
- Permissive licensing (MIT, Apache 2.0) is now the norm; the "research-only"
  restriction in early open releases has been largely abandoned.

## Foundation Model Releases

247 new foundation models were tracked in 2024 — a 38% increase over 2023. Of these:
- 119 were language-only models
- 76 were multimodal (image + text or more modalities)
- 52 were specialized (code, biology, law, etc.)

The United States remains home to the most valued AI companies (17 of the top 20
by private valuation) but China narrowed the gap on raw model release counts.
