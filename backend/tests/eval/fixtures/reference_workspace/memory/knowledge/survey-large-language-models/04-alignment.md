---
title: "LLM Survey: Alignment"
parent: knowledge/survey-large-language-models/index.md
section_index: 4
tags: [llm, alignment, rlhf, constitutional-ai, safety, fine-tuning, helpfulness]
created_at: 2026-04-01
updated_at: 2026-04-01
word_count: 480
---

# LLM Survey — Alignment

## What Is Alignment?

Alignment is the effort to ensure that an AI system's goals and behaviors match
human values and intended purpose. For LLMs, alignment primarily addresses three
properties (Anthropic's HHH framework):

- **Helpful**: The model assists users with their genuine needs.
- **Harmless**: The model avoids producing harmful outputs.
- **Honest**: The model does not deceive users or make unsupported claims.

## Reinforcement Learning from Human Feedback (RLHF)

RLHF is the dominant alignment technique for conversational LLMs:

1. **Supervised Fine-Tuning (SFT)**: Train the model on high-quality human-written
   examples of good assistant behavior.
2. **Reward Model Training**: Have human labellers compare pairs of model outputs
   and train a reward model to predict human preferences.
3. **PPO/RLHF Update**: Fine-tune the SFT model using the reward model as a
   surrogate for human feedback, via proximal policy optimization.

**Limitations of RLHF**:
- Expensive: requires human labellers at scale.
- Labeller variation: different people have different preferences.
- Reward hacking: the model can learn to maximize the reward model proxy rather
  than genuine human satisfaction ("Goodhart's Law in AI").

## Constitutional AI (Anthropic)

Constitutional AI (CAI) is an alternative/complement to RLHF:
1. Define a set of **principles** (the "constitution") for desired behavior.
2. Use the LLM itself to critique and revise its own outputs according to the
   principles, generating training data.
3. Train a preference model using this AI-generated feedback (RLAIF — RL from
   AI Feedback).

Advantages over RLHF:
- Less reliance on human labellers for harmlessness evaluation.
- The principles are explicit and auditable.
- Can be extended in a policy-consistent way.

## Direct Preference Optimization (DPO)

DPO (Rafailov et al., 2023) is a recently popular alternative to RLHF that:
- Skips the explicit reward model training step.
- Directly optimizes the LLM on preference pairs using a classification objective.
- Is simpler to train and more stable than PPO-based RLHF.

## Alignment and Safety Limitations

Current alignment methods address surface behaviors but have known limitations:
- **Jailbreaks**: Adversarial prompts can bypass safety training.
- **Distributional shift**: Models may behave unsafely in out-of-distribution
  contexts not covered by alignment training.
- **Capability-safety gap**: Safety training may not scale as well as capability
  training — a larger, more capable model is not automatically safer.
- **Honest uncertainty**: Models frequently express confident-sounding claims for
  facts they are likely to hallucinate; calibrating model uncertainty remains an
  active research challenge.
