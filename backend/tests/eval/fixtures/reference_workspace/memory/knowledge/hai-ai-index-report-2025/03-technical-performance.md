---
title: "HAI 2025: Technical Performance"
parent: knowledge/hai-ai-index-report-2025/index.md
section_index: 3
tags: [ai, benchmarks, performance, multimodal, reasoning]
created_at: 2026-04-01
updated_at: 2026-04-01
word_count: 510
---

# Technical Performance

## Benchmark Progress and Saturation

AI systems are rapidly saturating established benchmarks, raising important questions
about how to measure progress rigorously.

| Benchmark | AI Score 2023 | AI Score 2024 | Human Avg |
|-----------|--------------|--------------|-----------|
| MMLU       | 86.4%        | 89.0%        | 88.6%     |
| HumanEval  | 84.1%        | 92.7%        | ~65%      |
| GSM8K      | 93.0%        | 97.1%        | ~60%      |
| MATH       | 72.6%        | 86.3%        | ~40%      |

For the first time ever, AI performance on MMLU **exceeded average human performance**
(89.0% vs 88.6%) in 2024, though top-quartile human scores remain higher.

## Reasoning and Science Benchmarks

- FrontierMath (competition-level mathematics) saw AI solutions jump from <2% to
  25.1% in 2024 — still well below human expert performance (~75%).
- On the GPQA (Graduate-level science Q&A) benchmark, the best AI systems reached
  72.3%, approaching domain-expert human performance (81.2%).

## Multimodal Capabilities

Image-text models achieved human-level or super-human performance on:
- DocVQA (document question answering): 92.6% (human: 89.0%)
- ChartQA (chart understanding): 87.4%
- Visual CoT (multi-step visual reasoning): 68.0% (humans: 83.0% — still a gap)

Video understanding emerged as a growing capability area; best 2024 models can
answer temporal questions about 10-minute videos with ~74% accuracy.

## Agentic AI Performance

Long-horizon task-completion benchmarks measuring multi-step autonomous behavior
showed rapid progress:
- SWE-bench (real software bugs): 0.5% (2023) → 13.9% (2024)
- WebArena (web navigation): 10.8% → 31.5%

These gains come with caveats: benchmarks assume a supportive environment and do not
measure real-world reliability or robustness.

## Cost of Intelligence

The cost of running AI inference per "effective unit of task completion" fell roughly
10-fold between 2023 and 2024, democratizing access to capable models for developers
and small businesses.
