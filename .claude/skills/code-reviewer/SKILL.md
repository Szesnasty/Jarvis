---
name: code-reviewer
description: >
  Perform thorough code reviews. Use when reviewing pull requests, auditing code quality,
  checking for security issues, or when asked to review code. Covers TypeScript, JavaScript,
  Python, Go, Swift, and Kotlin.
---

# Code Review

When reviewing code, follow this structured process:

## 1. Read First, Judge Second

Read all changed files completely before writing any feedback. Understand the intent and context before critiquing details.

## 2. Categorize Findings by Severity

- **Critical** — Security vulnerabilities, data loss risks, correctness bugs
- **High** — Performance issues that will bite in production, error handling gaps, race conditions
- **Medium** — API design issues, missing validation at system boundaries, type safety gaps
- **Low** — Style inconsistencies, naming, minor readability improvements

## 3. What to Check

### Correctness
- Does the code do what it claims to do?
- Are edge cases handled (null, empty, boundary values)?
- Are error paths tested and recoverable?

### Security
- Input validation at system boundaries (user input, external APIs)
- SQL injection, XSS, command injection risks
- Secrets or credentials in code
- Dependency vulnerabilities

### Architecture
- Does this change belong in this module?
- Are the abstractions at the right level?
- Will this be maintainable in 6 months?
- Does it follow the existing patterns in the codebase?

### Performance
- O(n²) or worse in hot paths?
- Unbounded queries or collections?
- Missing indexes on queried fields?
- Unnecessary allocations in loops?

### Testing
- Are the critical paths covered?
- Do tests verify behavior, not implementation?
- Are edge cases and error paths tested?

## 4. How to Give Feedback

- Lead with the specific file and line
- State what the issue is, not just that there is one
- Explain WHY it matters, not just that it's wrong
- Suggest a fix when possible
- Distinguish between "must fix" and "consider changing"

## 5. Output Format

```markdown
## Code Review: [component/feature name]

**Overall Assessment**: [Good | Needs Work | Critical Issues] — one sentence summary

### Critical Issues
[numbered list or "None found"]

### High Priority
[numbered list with file:line references]

### Medium Priority
[numbered list]

### Low Priority
[numbered list]

### Architecture Positives
[what's done well — always include this]

### Recommended Priorities
[ordered list of what to fix first]
```

## Rules

- Never nitpick formatting if a linter/formatter exists
- Don't suggest adding features beyond the scope of the change
- If the code is good, say so — don't manufacture issues
- One real bug is worth more than ten style comments
- After making any code changes, check `docs/.registry.json` and update corresponding documentation. This is part of the project's Definition of Done.
