"""Reference evaluation queries targeting the four Step 27 reference PDFs.

33 queries split across six types:
  factual        (8) — direct factual lookup in a single document
  cross_doc      (6) — require synthesising information across >= 2 documents
  section_typed  (8) — explicitly target content of a known section type
  polish         (4) — Polish language queries against English documents
  numerical      (4) — require retrieving specific numbers or statistics
  client_estimate(3) — added in step 28e; target section-typed content for
                       the Client Estimator workflow

Each entry:
  query              — the question as a user would phrase it
  type               — one of the six types above
  expected_paths     — list of section paths that should be in top-5 results
  min_recall         — per-query recall floor for the CI gate (0.0 = informational only)
  notes              — brief rationale
"""

REFERENCE_QUERIES: list[dict] = [
    # ─────────────────────────────────────────────────
    # FACTUAL  (8)
    # ─────────────────────────────────────────────────
    {
        "query": "what does the OWASP top 10 say about prompt injection?",
        "type": "factual",
        "expected_paths": [
            "knowledge/owasp-llm-top-10/02-llm01-prompt-injection.md",
        ],
        "min_recall": 1.0,
        "notes": "Primary prompt injection section should rank first.",
    },
    {
        "query": "what is excessive agency in LLM applications?",
        "type": "factual",
        "expected_paths": [
            "knowledge/owasp-llm-top-10/06-llm08-excessive-agency.md",
        ],
        "min_recall": 1.0,
        "notes": "LLM08 Excessive Agency is the sole authoritative section.",
    },
    {
        "query": "NIST AI RMF Govern function responsibilities",
        "type": "factual",
        "expected_paths": [
            "knowledge/nist-ai-rmf/02-govern.md",
        ],
        "min_recall": 1.0,
        "notes": "Govern section contains all GV-x categories.",
    },
    {
        "query": "emergent abilities in large language models threshold",
        "type": "factual",
        "expected_paths": [
            "knowledge/survey-large-language-models/03-emergent-abilities.md",
        ],
        "min_recall": 1.0,
        "notes": "Emergence section lists scale thresholds per capability.",
    },
    {
        "query": "chain-of-thought prompting technique steps",
        "type": "factual",
        "expected_paths": [
            "knowledge/survey-large-language-models/05-prompting-techniques.md",
        ],
        "min_recall": 1.0,
        "notes": "Prompting section explains CoT with examples.",
    },
    {
        "query": "sensitive information disclosure LLM system prompt extraction",
        "type": "factual",
        "expected_paths": [
            "knowledge/owasp-llm-top-10/05-llm06-sensitive-information-disclosure.md",
        ],
        "min_recall": 1.0,
        "notes": "LLM06 covers system prompt extraction attacks.",
    },
    {
        "query": "NIST AI RMF red-teaming and bias measurement",
        "type": "factual",
        "expected_paths": [
            "knowledge/nist-ai-rmf/04-measure.md",
        ],
        "min_recall": 1.0,
        "notes": "Measure function MS-1 explicitly covers red-teaming.",
    },
    {
        "query": "RAG retrieval augmented generation prompting",
        "type": "factual",
        "expected_paths": [
            "knowledge/survey-large-language-models/05-prompting-techniques.md",
        ],
        "min_recall": 1.0,
        "notes": "RAG section is in the prompting chapter.",
    },

    # ─────────────────────────────────────────────────
    # CROSS-DOCUMENT  (6)
    # ─────────────────────────────────────────────────
    {
        "query": "how do NIST RMF and OWASP overlap on data poisoning?",
        "type": "cross_doc",
        "expected_paths": [
            "knowledge/nist-ai-rmf/02-govern.md",
            "knowledge/owasp-llm-top-10/04-llm03-training-data-poisoning.md",
        ],
        "min_recall": 0.5,
        "notes": "OWASP LLM03 and NIST Govern both address data provenance.",
    },
    {
        "query": "prompt injection and NIST AI risk management mitigation",
        "type": "cross_doc",
        "expected_paths": [
            "knowledge/owasp-llm-top-10/02-llm01-prompt-injection.md",
            "knowledge/nist-ai-rmf/05-manage.md",
        ],
        "min_recall": 0.5,
        "notes": "Manage function covers incident response for LLM attacks.",
    },
    {
        "query": "LLM safety risks alignment techniques comparison",
        "type": "cross_doc",
        "expected_paths": [
            "knowledge/survey-large-language-models/04-alignment.md",
            "knowledge/owasp-llm-top-10/01-overview.md",
        ],
        "min_recall": 0.5,
        "notes": "Alignment survey + OWASP overview together address safety.",
    },
    {
        "query": "AI compute growth investment 2024 global trends",
        "type": "cross_doc",
        "expected_paths": [
            "knowledge/hai-ai-index-report-2025/02-research-and-development.md",
            "knowledge/hai-ai-index-report-2025/04-economy-and-workforce.md",
        ],
        "min_recall": 0.5,
        "notes": "Compute growth (R&D section) and investment (economy section) are separate.",
    },
    {
        "query": "trustworthy AI requirements governance accountability transparency",
        "type": "cross_doc",
        "expected_paths": [
            "knowledge/nist-ai-rmf/01-introduction.md",
            "knowledge/nist-ai-rmf/02-govern.md",
        ],
        "min_recall": 0.5,
        "notes": "Trustworthy AI defined in intro; accountability in Govern.",
    },
    {
        "query": "open-source LLM models ecosystem releases",
        "type": "cross_doc",
        "expected_paths": [
            "knowledge/hai-ai-index-report-2025/02-research-and-development.md",
            "knowledge/survey-large-language-models/02-llm-families.md",
        ],
        "min_recall": 0.5,
        "notes": "HAI reports open-source growth; survey covers LLaMA/Mistral families.",
    },

    # ─────────────────────────────────────────────────
    # SECTION-TYPED  (8) — target specific section types
    # ─────────────────────────────────────────────────
    {
        "query": "what risks are listed for LLM deployments?",
        "type": "section_typed",
        "expected_paths": [
            "knowledge/owasp-llm-top-10/01-overview.md",
            "knowledge/owasp-llm-top-10/02-llm01-prompt-injection.md",
        ],
        "expected_section_types": ["risks"],
        "min_recall": 0.5,
        "notes": "Overview lists all 10 risks; injection section lists deployment risks.",
    },
    {
        "query": "mitigations for training data poisoning in LLMs",
        "type": "section_typed",
        "expected_paths": [
            "knowledge/owasp-llm-top-10/04-llm03-training-data-poisoning.md",
        ],
        "expected_section_types": ["mitigations"],
        "min_recall": 1.0,
        "notes": "LLM03 section has explicit Mitigations subsection.",
    },
    {
        "query": "AI governance policies and organizational risk tolerance",
        "type": "section_typed",
        "expected_paths": [
            "knowledge/nist-ai-rmf/02-govern.md",
        ],
        "expected_section_types": ["governance"],
        "min_recall": 1.0,
        "notes": "Govern GV-1 and GV-4 cover policies and risk tolerance.",
    },
    {
        "query": "GPT model architecture parameters training",
        "type": "section_typed",
        "expected_paths": [
            "knowledge/survey-large-language-models/02-llm-families.md",
        ],
        "expected_section_types": ["technical"],
        "min_recall": 1.0,
        "notes": "LLM families section covers all GPT variants with params.",
    },
    {
        "query": "AI benchmark performance evaluation saturation",
        "type": "section_typed",
        "expected_paths": [
            "knowledge/hai-ai-index-report-2025/03-technical-performance.md",
        ],
        "expected_section_types": ["technical"],
        "min_recall": 1.0,
        "notes": "Technical performance section covers benchmark saturation.",
    },
    {
        "query": "AI incident response handling decommissioning",
        "type": "section_typed",
        "expected_paths": [
            "knowledge/nist-ai-rmf/05-manage.md",
        ],
        "expected_section_types": ["process"],
        "min_recall": 1.0,
        "notes": "Manage MG-2 and MG-3 cover incident response and decommissioning.",
    },
    {
        "query": "RLHF reinforcement learning human feedback steps",
        "type": "section_typed",
        "expected_paths": [
            "knowledge/survey-large-language-models/04-alignment.md",
        ],
        "expected_section_types": ["technical"],
        "min_recall": 1.0,
        "notes": "Alignment section explains RLHF step by step.",
    },
    {
        "query": "AI workforce demand skills job market 2024",
        "type": "section_typed",
        "expected_paths": [
            "knowledge/hai-ai-index-report-2025/04-economy-and-workforce.md",
        ],
        "expected_section_types": ["statistics"],
        "min_recall": 1.0,
        "notes": "Economy section covers 35% skill demand growth.",
    },

    # ─────────────────────────────────────────────────
    # POLISH  (4)
    # ─────────────────────────────────────────────────
    {
        "query": "co OWASP mówi o prompt injection?",
        "type": "polish",
        "expected_paths": [
            "knowledge/owasp-llm-top-10/02-llm01-prompt-injection.md",
        ],
        "min_recall": 0.5,
        "notes": "Polish version of the primary prompt injection query.",
    },
    {
        "query": "jak NIST definiuje zaufane systemy AI?",
        "type": "polish",
        "expected_paths": [
            "knowledge/nist-ai-rmf/01-introduction.md",
        ],
        "min_recall": 0.5,
        "notes": "Polish query about NIST trustworthy AI definition.",
    },
    {
        "query": "jakie modele LLM są open source?",
        "type": "polish",
        "expected_paths": [
            "knowledge/survey-large-language-models/02-llm-families.md",
        ],
        "min_recall": 0.5,
        "notes": "Polish query about open-source LLM models.",
    },
    {
        "query": "wzrost inwestycji w AI w 2024 roku",
        "type": "polish",
        "expected_paths": [
            "knowledge/hai-ai-index-report-2025/04-economy-and-workforce.md",
        ],
        "min_recall": 0.0,
        "notes": "Polish query about AI investment growth. min_recall=0 as hard cross-lingual.",
    },

    # ─────────────────────────────────────────────────
    # NUMERICAL  (4)
    # ─────────────────────────────────────────────────
    {
        "query": "what was the AI training compute growth in 2024 per HAI?",
        "type": "numerical",
        "expected_paths": [
            "knowledge/hai-ai-index-report-2025/02-research-and-development.md",
        ],
        "min_recall": 1.0,
        "notes": "R&D section states 2-3x compute growth between 2023 and 2024.",
    },
    {
        "query": "how many AI-related incidents were tracked in 2024?",
        "type": "numerical",
        "expected_paths": [
            "knowledge/hai-ai-index-report-2025/05-policy-and-governance.md",
        ],
        "min_recall": 1.0,
        "notes": "Policy section states 233 incidents in 2024.",
    },
    {
        "query": "global private AI investment total 2024 amount",
        "type": "numerical",
        "expected_paths": [
            "knowledge/hai-ai-index-report-2025/04-economy-and-workforce.md",
        ],
        "min_recall": 1.0,
        "notes": "Economy section states $252 billion total investment.",
    },
    {
        "query": "MMLU benchmark score AI versus human 2024",
        "type": "numerical",
        "expected_paths": [
            "knowledge/hai-ai-index-report-2025/03-technical-performance.md",
        ],
        "min_recall": 1.0,
        "notes": "Technical performance table shows 89.0% AI vs 88.6% human on MMLU.",
    },
    # ─────────────────────────────────────────────────
    # CLIENT_ESTIMATE  (3) — added in step 28e
    # These target section-typed content across the reference documents.
    # ─────────────────────────────────────────────────
    {
        "query": "summarize the OWASP LLM Top 10 risks in three bullets",
        "type": "client_estimate",
        "expected_paths": [
            "knowledge/owasp-llm-top-10/02-llm01-prompt-injection.md",
            "knowledge/owasp-llm-top-10/01-overview.md",
        ],
        "min_recall": 0.5,
        "notes": "Should surface the OWASP risks sections (section_type=risks).",
    },
    {
        "query": "what are the open questions in the HAI AI Index report?",
        "type": "client_estimate",
        "expected_paths": [
            "knowledge/hai-ai-index-report-2025/05-policy-and-governance.md",
            "knowledge/hai-ai-index-report-2025/01-executive-summary.md",
        ],
        "min_recall": 0.5,
        "notes": "Policy/governance section contains unresolved items and open questions.",
    },
    {
        "query": "what integrations does the NIST AI RMF require?",
        "type": "client_estimate",
        "expected_paths": [
            "knowledge/nist-ai-rmf/03-map.md",
            "knowledge/nist-ai-rmf/02-govern.md",
        ],
        "min_recall": 0.5,
        "notes": "MAP and GOVERN sections cover integration requirements for AI risk management.",
    },
]
