---
title: "LLM Survey: Emergent Abilities"
parent: knowledge/survey-large-language-models/index.md
section_index: 3
tags: [llm, emergent-abilities, scaling, capabilities, few-shot, reasoning]
created_at: 2026-04-01
updated_at: 2026-04-01
word_count: 430
---

# LLM Survey — Emergent Abilities

## Definition

**Emergent abilities** in LLMs are capabilities that appear **abruptly at
certain scales** and are essentially absent at smaller scales. They were not
explicitly trained for and were not predicted by linear interpolation from
smaller-scale results.

Wei et al. (2022) defined emergence as: "abilities that are not present in
smaller-scale models and are only present in larger-scale models."

## Examples of Emergent Abilities

| Ability | Approximate Scale Threshold |
|---------|---------------------------|
| Few-shot in-context learning | ~10B params |
| Multi-step arithmetic (CoT) | ~100B params |
| Code generation | ~1B, with quality scaling >10B |
| Instruction following without examples | ~1–10B with fine-tuning |
| Analogy reasoning | ~100B params |
| Calibrated uncertainty | Still improving at frontier scale |
| Multi-hop factual QA | ~50B params |

## Controversy and Reanalysis

Schaeffer et al. (2023) challenged the emergence narrative, arguing that
apparent emergence may be an artifact of **discontinuous evaluation metrics**.
When continuous metrics are used (e.g., mean log-probability instead of accuracy),
performance improvements appear smooth rather than sudden.

This debate has important implications: if emergence is metric-dependent, the claim
that capabilities "appear unexpectedly" may overstate the difficulty of capability
prediction and safety forecasting.

## Emergent Abilities and Safety

The emergence phenomenon has significant implications for AI safety:
1. **Capability surprise**: If important capabilities emerge unpredictably, safety
   evaluations performed at smaller scales may miss risks that arise at deployment scale.
2. **Benchmark saturation**: Emergent capabilities can cause sudden benchmark jumps,
   making it harder to use benchmarks as reliable capability forecasts.
3. **Deceptive alignment risk**: Some researchers worry that goal-directed behavior
   inconsistent with training objectives could emerge at sufficient scale without
   being detected during training.

## Scaling Laws and Predictability

Scaling laws (Chinchilla study, Hoffmann et al. 2022) show that for a given compute
budget:
- Optimal balance: equal scaling of model size and tokens (~20 tokens/parameter).
- PaLM, GPT-4, and frontier 2024 models appear to follow the Chinchilla-optimal
  or even data-efficient regime.
- Next-token prediction loss decreases smoothly with compute, even when task-specific
  performance shows step-change improvements.
