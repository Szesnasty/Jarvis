"""Synthetic evaluation corpus for retrieval benchmarking."""

EVAL_CORPUS = [
    {
        "path": "projects/website-redesign.md",
        "content": """---
title: Website Redesign Project
tags: [project, web, design]
people: [Michał Kowalski, Anna]
created_at: 2026-03-01
---

## Goals
Redesign the company website by Q2. Focus on mobile-first design and faster page loads.

## Meeting Notes
Met with Michał about the new landing page. He wants hero section with animated gradient.
Anna suggested using a card-based layout for the portfolio section.
We agreed to prototype three variants by next Friday.

## Technical Decisions
- Framework: Nuxt 3
- Hosting: Vercel
- CMS: Markdown files
- Design system: custom tokens + Tailwind

Related: [[travel/conference-notes.md]]
""",
    },
    {
        "path": "health/sleep-tracking.md",
        "content": """---
title: Sleep Tracking Observations
tags: [health, sleep, tracking]
created_at: 2026-02-15
---

## Current Setup
Using Oura Ring Gen 3 for sleep tracking. Average sleep score: 78.

## Patterns Noticed
- Deep sleep drops below 1h when I drink coffee after 2pm
- Best sleep scores correlate with evening walks
- Screen time after 10pm consistently reduces REM by 15-20min
- Weekend sleep debt recovery takes 2-3 days

## Action Items
- No caffeine after 1pm (strict rule)
- 20min walk after dinner
- Blue light glasses after 9pm

Related: [[health/evening-routine.md]], [[health/supplements.md]]
""",
    },
    {
        "path": "health/evening-routine.md",
        "content": """---
title: Evening Routine Protocol
tags: [health, routine, habits]
created_at: 2026-02-20
---

## Current Routine
1. 7:30pm - Dinner (no heavy carbs)
2. 8:00pm - Walk outside (20-30min)
3. 8:30pm - Reading or light conversation
4. 9:00pm - Blue light glasses on
5. 9:30pm - Magnesium supplement
6. 10:00pm - Lights dimmed, journal entry
7. 10:30pm - In bed, no devices

## Why This Works
The routine creates a wind-down signal for the body. Consistent timing helps circadian rhythm.
Magnesium glycinate (400mg) noticeably improves sleep onset time.

## Adjustments
- On travel days, compress to 1h routine starting 9:30pm
- Social events: skip walk, keep supplements
""",
    },
    {
        "path": "health/supplements.md",
        "content": """---
title: Supplement Stack
tags: [health, supplements]
created_at: 2026-01-10
---

## Current Stack
- Vitamin D3: 4000 IU (morning with fat)
- Omega-3: 2g EPA/DHA (with meals)
- Magnesium Glycinate: 400mg (evening)
- Creatine: 5g (morning)
- Vitamin K2: 100mcg (with D3)

## Evidence Notes
D3+K2 combo supported by multiple studies for bone health.
Magnesium for sleep quality — see [[health/sleep-tracking.md]].
Creatine cognitive benefits emerging in literature.

## Blood Work Results (Feb 2026)
- Vitamin D: 62 ng/mL (optimal)
- B12: 580 pg/mL (normal)
- Iron: slightly low, considering supplementation
""",
    },
    {
        "path": "people/michal-kowalski.md",
        "content": """---
title: Michał Kowalski
tags: [person, colleague, engineering]
created_at: 2026-01-05
---

## About
Senior frontend developer. Works with me on the website redesign project.
Known for strong opinions on UX and animation.

## Key Interactions
- 2026-03-01: Discussed landing page design, wants hero animation
- 2026-02-15: Code review session on component library
- 2026-01-20: Planning meeting for Q1 sprint

## Notes
- Prefers Vue over React
- Expert in CSS animations and SVG
- Recommended vis-network for graph visualization
- Birthday: April 12

Related: [[projects/website-redesign.md]]
""",
    },
    {
        "path": "people/anna-nowak.md",
        "content": """---
title: Anna Nowak
tags: [person, designer, colleague]
created_at: 2026-01-05
---

## About
UX designer. Focused on user research and accessibility.

## Key Interactions
- 2026-03-01: Website redesign kickoff, suggested card-based portfolio
- 2026-02-28: Shared accessibility audit results
- 2026-02-10: Workshop on design tokens

## Design Philosophy
- Mobile-first always
- Accessibility is not optional
- Data-driven decisions over personal preference
""",
    },
    {
        "path": "people/kasia-wisniewska.md",
        "content": """---
title: Kasia Wiśniewska
tags: [person, friend, travel]
created_at: 2026-01-15
---

## About
Travel buddy and photographer. Planning trips together since 2024.

## Trips Together
- 2025 summer: Greece (Crete) — amazing food, great hiking
- 2025 winter: Japan (Tokyo, Kyoto) — cherry blossom timing was perfect
- 2026 planned: Portugal (Lisbon, Porto, Algarve)

## Notes
- Vegetarian, always needs restaurant research
- Excellent at finding off-the-beaten-path spots
- Shares photography tips

Related: [[travel/portugal-planning.md]]
""",
    },
    {
        "path": "travel/portugal-planning.md",
        "content": """---
title: Portugal Trip Planning
tags: [travel, planning, portugal]
people: [Kasia Wiśniewska]
created_at: 2026-03-10
---

## Overview
Two-week trip planned for June 2026.
Traveling with Kasia.

## Itinerary Draft
- Days 1-4: Lisbon (Alfama, Belém, day trip to Sintra)
- Days 5-7: Porto (wine cellars, Douro Valley day trip)
- Days 8-11: Algarve (beaches, Lagos, Sagres)
- Days 12-14: Back to Lisbon, departure

## Budget
- Flights: ~€300 round trip
- Accommodation: €60-80/night (Airbnb)
- Food: €30-40/day
- Total estimate: €2000-2500 per person

## Research Needed
- Best vegetarian restaurants in Lisbon and Porto (for Kasia)
- Hiking trails near Sagres
- Fado music venues
""",
    },
    {
        "path": "travel/conference-notes.md",
        "content": """---
title: VueConf 2026 Notes
tags: [conference, vue, tech, travel]
people: [Evan You]
created_at: 2026-02-25
---

## Key Talks
1. Evan You: Vue 3.5 and the future of reactivity
   - Vapor mode is production-ready
   - New compiler optimizations reduce bundle by 30%

2. State Management Patterns
   - Pinia alternatives explored
   - Composable-first architecture gaining traction

3. AI in Frontend Development
   - Code generation tools for Vue components
   - Accessibility testing with AI

## Takeaways
- Try Vapor mode in the website redesign project
- Consider dropping Pinia in favor of useState composables
- Set up automated a11y testing pipeline

Related: [[projects/website-redesign.md]]
""",
    },
    {
        "path": "projects/jarvis-development.md",
        "content": """---
title: Jarvis AI Assistant Development
tags: [project, ai, development]
created_at: 2026-01-01
---

## Vision
Build a voice-first personal memory and knowledge system.
Local-first, Obsidian-compatible, powered by Claude API.

## Architecture
- Frontend: Nuxt 3 + TypeScript
- Backend: FastAPI + SQLite
- Voice: Web Speech API (MVP)
- Knowledge Graph: local JSON

## Current Progress
- Phase 1 complete: onboarding, basic chat
- Phase 2 in progress: memory + retrieval
- Hybrid retrieval pipeline working (BM25 + embeddings + graph)

## Key Decisions
- No vector database, use local fastembed
- Markdown as source of truth
- SQLite as operational index only
""",
    },
    {
        "path": "areas/productivity.md",
        "content": """---
title: Productivity System
tags: [area, productivity, planning]
created_at: 2026-01-01
---

## My System
1. Weekly planning every Sunday evening
2. Daily 3 priorities (not tasks — outcomes)
3. Time blocking in 90-min deep work sessions
4. Review and reflect every Friday

## Tools
- Obsidian for notes and knowledge
- Jarvis for voice capture and retrieval
- Calendar for time blocks
- Physical notebook for daily priorities

## What Works
- Morning deep work (before 11am) is 3x more productive
- Batch communication (email/Slack) to 2 windows per day
- Say no to meetings without agenda

## What Doesn't Work
- Todo apps with 100+ items
- Multitasking (context switching cost is real)
- Planning more than 2 weeks ahead in detail
""",
    },
    {
        "path": "areas/learning.md",
        "content": """---
title: Learning Goals 2026
tags: [area, learning, goals]
created_at: 2026-01-01
---

## Active Learning
1. **Rust** — systems programming, building CLI tools
2. **Machine Learning** — practical NLP for Jarvis
3. **Photography** — composition and lighting (with Kasia's tips)

## Resources
- Rust: "Programming Rust" book + Exercism
- ML: fast.ai course + Andrej Karpathy lectures
- Photography: YouTube + practice

## Schedule
- Rust: 3x/week, 1h sessions
- ML: weekends, 2h blocks
- Photography: practice during walks and travel

## Progress Tracking
- Rust: finished ownership chapter, building first CLI tool
- ML: completed fast.ai lesson 4
- Photography: 200 photos edited, starting to see improvement
""",
    },
    {
        "path": "daily/2026-03-15.md",
        "content": """---
title: Daily Note - March 15, 2026
tags: [daily]
created_at: 2026-03-15
---

## Morning
- Good sleep score (84), magnesium seems to be working
- Deep work session on Jarvis retrieval pipeline
- Fixed BM25 scoring bug that was penalizing long notes

## Afternoon
- Met with Michał about component library architecture
- He showed new CSS animation approach for the landing page
- Discussed with Anna about a11y testing automation

## Evening
- 30min walk, listened to Huberman podcast on dopamine
- Reviewed Portugal trip options with Kasia over video call
- She found amazing vegetarian restaurant in Alfama

## Tasks Done
- [x] Fix BM25 scoring
- [x] Review Michał's PR
- [x] Send Anna the a11y testing tools list
- [ ] Write weekly summary (moved to tomorrow)
""",
    },
    {
        "path": "daily/2026-03-16.md",
        "content": """---
title: Daily Note - March 16, 2026
tags: [daily]
created_at: 2026-03-16
---

## Morning
- Weekly planning session
- Priorities: ship Jarvis semantic search, finalize Portugal itinerary, complete Rust CLI project

## Work
- Implemented chunk-based retrieval for Jarvis
- Added entity canonicalization to reduce graph duplicates
- Tests passing, retrieval quality noticeably better

## Personal
- Ordered new running shoes (Hoka Clifton 9)
- Meal prepped for the week (5 lunches)
- Read 30 pages of "Programming Rust"

## Reflection
Semantic search is a game-changer. Notes that were "hidden" in the vault now surface naturally.
The chunk approach means even long notes with multiple topics get matched correctly.
""",
    },
    {
        "path": "plans/q2-2026.md",
        "content": """---
title: Q2 2026 Plan
tags: [plan, quarterly]
created_at: 2026-03-20
---

## Professional Goals
1. Ship website redesign (with Michał and Anna)
2. Launch Jarvis voice interface (Phase 3)
3. Complete Rust CLI tool for data processing

## Personal Goals
1. Portugal trip with Kasia (June)
2. Establish consistent running habit (3x/week)
3. Complete fast.ai course
4. Improve sleep score average to 85+

## Key Metrics
- Website: launch by May 31
- Jarvis: voice working by April 30
- Running: log 50km by end of Q2
- Sleep: track weekly averages
""",
    },
    {
        "path": "knowledge/retrieval-systems.md",
        "content": """---
title: Information Retrieval Methods
tags: [knowledge, ir, search]
created_at: 2026-02-01
---

## BM25
Classic probabilistic ranking function. Works well for keyword matching.
- TF-IDF based but with saturation
- Length normalization prevents bias toward long documents
- Parameters k1=1.5, b=0.75 are good defaults

## Dense Retrieval
Neural embeddings for semantic similarity.
- Encode queries and documents into vector space
- Cosine similarity for ranking
- Works for paraphrases and conceptual matches
- Requires good embedding model

## Hybrid Approaches
Combine sparse (BM25) and dense (embedding) signals.
- Reciprocal rank fusion
- Weighted linear combination
- Re-ranking pipelines (coarse → fine)

## Graph-Augmented Retrieval
Use knowledge graph to expand context.
- Entity linking → graph traversal → neighbor documents
- Especially good for relational queries ("what did X say about Y")
""",
    },
    {
        "path": "knowledge/graph-theory-basics.md",
        "content": """---
title: Graph Theory for Knowledge Graphs
tags: [knowledge, graph, theory]
created_at: 2026-02-10
---

## Core Concepts
- Nodes represent entities (people, topics, documents)
- Edges represent relationships
- Weighted edges can encode relationship strength

## Community Detection
Finding clusters of densely connected nodes.
- Louvain algorithm: greedy modularity optimization
- Label propagation: fast but non-deterministic
- Useful for topic clustering in knowledge graphs

## Centrality Measures
Which nodes are most "important"?
- Degree centrality: most connections
- Betweenness: bridges between communities
- PageRank: recursive importance

## Entity Resolution
Merging duplicate entities (same real-world thing, different labels).
- String similarity (Jaro-Winkler, Levenshtein)
- Context-based: do they appear in similar contexts?
- Alias tables for manual mappings
""",
    },
    {
        "path": "inbox/quick-thought-running.md",
        "content": """---
title: Running Thoughts
tags: [running, health, fitness]
created_at: 2026-03-14
---

Should I train for a half marathon this year? Kasia mentioned she's interested too.
Current fitness: can run 8km comfortably, 10km with effort.
Need to build up gradually — maybe follow a 12-week plan.
Ask about running routes near the coast during Portugal trip.
""",
    },
    {
        "path": "preferences/writing-style.md",
        "content": """---
title: Writing Style Preferences
tags: [preference, style]
created_at: 2026-01-01
---

## General Rules
- Be concise, not verbose
- Use bullet points for lists
- Prefer active voice
- No corporate jargon
- Polish language: use informal "ty" not formal "Pan/Pani"

## Planning Output
- Always include specific dates when available
- Group by priority (urgent / this week / later)
- Include estimated time for each task

## Summary Style
- Start with one-line TL;DR
- Key points as bullets
- Action items at the end
""",
    },
    {
        "path": "daily/2026-03-17-pl.md",
        "content": """---
title: Notatka dzienna - 17 marca 2026
tags: [daily, polski]
created_at: 2026-03-17
---

## Rano
- Dobry sen (wynik 82), magnesium ciągle działa
- Sesja głębokiej pracy nad grafem wiedzy w Jarvisie
- Dodałem kanonizację encji — graf jest teraz dużo czystszy

## Popołudnie
- Rozmowa z Kasią o Portugalii — rezerwacja lotów do Lizbony
- Cena €280 za osobę, lot bezpośredni z Krakowa
- Zarezerwowaliśmy pierwszy Airbnb w Alfamie

## Wieczór
- Bieganie 6km, nowy rekord tempa (5:30/km)
- Kolacja: makaron z warzywami
- Czytanie "Programming Rust" — rozdziały o trait'ach

## Przemyślenia
Kanonizacja encji naprawdę pomaga. "Michał" i "Michał Kowalski" to teraz ten sam węzeł.
Trzeba jeszcze dodać aliasy dla Kasi — "Kasia" vs "Kasia Wiśniewska".
""",
    },
]
