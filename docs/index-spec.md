# Jarvis — Implementation Spec Index

> **Master tracking file.** Every step links here. Check off when DoD is met.

---

## References

- [JARVIS-PLAN.md](JARVIS-PLAN.md) — Full project plan
- [CODING-GUIDELINES.md](CODING-GUIDELINES.md) — Coding rules (Python + Vue)

---

## Definition of Done (Global)

Every step is considered **done** only when ALL of the following are true:

1. All files listed in the step spec are created/modified
2. All tests pass (`pytest` for backend, `vitest` for frontend)
3. No lint errors
4. All acceptance criteria from the step spec are checked off
5. Code committed with descriptive message
6. This index updated with ✅

---

## Phase 1 — System Skeleton

- [x] [Step 01 — Backend Init (FastAPI)](steps/step-01-backend-init.md)
- [ ] [Step 02 — Frontend Init (Vue + Vite)](steps/step-02-frontend-init.md)
- [ ] [Step 03 — Onboarding + Workspace Creation](steps/step-03-onboarding-workspace.md)

## Phase 2 — Local Memory

- [ ] [Step 04 — Memory Service + SQLite Index](steps/step-04-memory-service.md)

## Phase 3 — Claude API

- [ ] [Step 05 — Claude API + Streaming + Tools](steps/step-05-claude-integration.md)

## Phase 4 — Voice

- [ ] [Step 06 — Voice Input/Output + States](steps/step-06-voice.md)

## Phase 5 — Planning & Operational Memory

- [ ] [Step 07 — Planning Tools + Session Persistence](steps/step-07-planning-ops.md)

## Phase 6 — Knowledge Graph

- [ ] [Step 08 — Knowledge Graph + Retrieval](steps/step-08-knowledge-graph.md)

## Phase 7 — Specialists

- [ ] [Step 09 — Specialist System + UI Wizard](steps/step-09-specialists.md)

## Phase 8 — Polish

- [ ] [Step 10 — Polish, Obsidian, Caching, Ingest](steps/step-10-polish.md)

---

## Progress Log

| Date | Step | Status | Commit |
|------|------|--------|--------|
| 2026-04-12 | Step 01 | ✅ Done | `feat: step-01 backend init` |
