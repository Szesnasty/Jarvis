---
title: "LLM Survey: Prompting Techniques"
parent: knowledge/survey-large-language-models/index.md
section_index: 5
tags: [llm, prompting, few-shot, chain-of-thought, rag, in-context-learning]
created_at: 2026-04-01
updated_at: 2026-04-01
word_count: 440
---

# LLM Survey — Prompting Techniques

## Overview

Prompting is the method by which users and developers communicate task instructions
to LLMs at inference time without modifying model weights. The art and science of
writing effective prompts has become central to LLM application development.

## Zero-Shot Prompting

Provide a task description and input with no examples:
```
Translate the following English text to French:
Text: "The weather is nice today."
Translation:
```
Work surprisingly well for tasks well-represented in training data. Fail for unusual
formats or tasks requiring specific structural knowledge.

## Few-Shot In-Context Learning

Provide 1–8 worked examples before the actual input:
```
Positive: "I love this product!"
Label: positive

Negative: "The quality is terrible."
Label: negative

Text: "Delivery was fast but packaging was damaged."
Label:
```
Few-shot prompting dramatically improves performance on classification, extraction,
and format-following tasks, especially for models ≥7B parameters.

## Chain-of-Thought (CoT) Prompting

Encourage the model to generate intermediate reasoning steps before the final answer:
```
Q: Roger had 5 tennis balls. He bought 2 cans of tennis balls.
Each can has 3 balls. How many balls does he have now?
A: Roger started with 5. He bought 2 × 3 = 6 more. 5 + 6 = 11. The answer is 11.
```
CoT prompting emerged as a key technique for multi-step arithmetic and reasoning
tasks, and correlates strongly with the emergent ability threshold around 100B params.

## Retrieval-Augmented Generation (RAG)

RAG combines the parametric knowledge of an LLM with a non-parametric external
knowledge source (a document store):

1. **Retrieve**: Given the user query, search a document store for relevant passages.
2. **Augment**: Concatenate retrieved passages with the original query as context.
3. **Generate**: The LLM generates a response grounded in the retrieved context.

**Key advantages**:
- Reduces hallucination on factual questions by providing ground truth.
- Allows knowledge updates without retraining the model.
- Enables domain-specific knowledge injection at low cost.

**Key challenges**:
- Retrieval quality bottlenecks the overall response quality.
- Long-context retrieval (many retrieved documents) increases latency and cost.
- Indirect prompt injection (OWASP LLM01) is a risk when retrieved content is
  adversarial — the model may execute instructions embedded in retrieved documents.

## Prompt Injection in Context

Prompting techniques and security interact significantly. The techniques above all
expand the attack surface covered in OWASP LLM01:
- Few-shot examples in the system prompt can be hijacked by adversarial examples
  injected into the example set.
- CoT reasoning can be exploited to produce rational-sounding justifications for
  harmful outputs.
- RAG introduces indirect prompt injection as a primary attack vector.
