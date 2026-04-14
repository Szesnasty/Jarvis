---
name: review-codebase
description: >
  Run a full codebase review across all features. Reads the documentation registry
  to understand feature boundaries, then spawns code-reviewer agents per feature to
  identify bugs, security issues, and quality concerns. Non-breaking — reports issues
  and optionally applies safe fixes only. Invoke with /review-codebase.
---

# Codebase Review

You are the **orchestrator** for a full codebase review. Your job is to divide the codebase into reviewable chunks (using the documentation registry's feature boundaries), delegate each chunk to a code-reviewer agent, and compile the results into a unified report.

## How It Works

### Step 1: Read the registry

Read `docs/.registry.json` to get the feature map. Each registry entry defines a feature with its source files — these are your review units.

If no registry exists, tell the user to run `codument scan` first.

### Step 2: Determine review scope

By default, review **all features**. The user may narrow scope:
- Specific features: "review auth and payments"
- By status: "review stale features only"
- By directory: "review everything under src/api/"
- By severity filter: "only critical and high issues"

If the user doesn't specify, review everything.

### Step 3: Spawn code-reviewer agents

For each feature in scope, spawn a **code-reviewer agent** with specific instructions:

```
Review the "{feature-name}" feature.
Doc: {doc path from registry}
Source files to review:
{list each file from the registry entry's sources array}

Focus areas: correctness, security, performance, error handling, type safety.
Report findings by severity: Critical, High, Medium, Low.
Include a Positives section for what's done well.
{any user-specified focus or constraints}
```

**Batching:**
- Small projects (< 6 features): spawn all agents in parallel
- Larger projects: batch 3-5 agents at a time to avoid overwhelming the system

**Important:** Be specific in agent instructions. Include the exact file paths. Vague instructions produce vague reviews.

### Step 4: Compile the report

After all agents complete, compile findings into a unified report:

```markdown
# Codebase Review Report

**Date**: YYYY-MM-DD
**Features reviewed**: N
**Total findings**: N (X critical, Y high, Z medium, W low)

## Critical Issues
[all critical findings across features, grouped by feature]

## High Priority
[all high findings across features, grouped by feature]

## Medium Priority
[all medium findings, grouped by feature]

## Low Priority
[summary count only — detail available per-feature]

## Highlights
[notable positives across the codebase]

## Recommended Priorities
[ordered list: what to fix first based on severity and blast radius]
```

### Step 5: Optionally apply safe fixes

If the user asks to fix issues (or says "fix what you can"):
1. Only fix **Critical** and **High** issues
2. Only apply **non-breaking changes**: bug fixes, missing null checks, error handling, security patches
3. **Never**: rename public APIs, change function signatures, refactor architecture, remove exports
4. After fixes, run the project's test suite to verify nothing broke
5. Update `docs/.registry.json` if any source files were modified — mark affected features as `"stale"` so docs get updated

If uncertain whether a fix is safe, **report it instead of applying it**.

## What This Is NOT

- Not a refactoring tool — don't suggest "this should be rewritten"
- Not a style checker — assume linters handle formatting
- Not an architecture review — that's the senior-architect skill
- Not a PR review — this reviews the whole codebase, not a diff

## Scope Control

The user can customize the review:

| User says | You do |
|-----------|--------|
| `/review-codebase` | Review all features in registry |
| `/review-codebase auth payments` | Review only named features |
| `/review-codebase --security` | Focus agents on security checks only |
| `/review-codebase --fix` | Review and apply safe fixes for critical/high |
| `/review-codebase --critical-only` | Only report critical severity |

Parse these from the user's message — they don't need to use exact flags.

## Rules

- Always read the registry first — don't guess at feature boundaries
- One agent per feature — don't overload agents with multiple features
- Report format is consistent across runs so findings can be compared over time
- Don't manufacture issues — if a feature is clean, say so
- Focus on things that could actually cause problems in production
- After making any code changes, check `docs/.registry.json` and update corresponding documentation. This is part of the Definition of Done.
