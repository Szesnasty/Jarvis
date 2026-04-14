---
name: senior-architect
description: >
  Design and evaluate software architecture. Use when designing system architecture,
  making technical decisions, evaluating trade-offs, planning migrations, or when asked
  to architect a solution. Covers web apps, APIs, databases, and distributed systems.
---

# Software Architecture

When making architectural decisions, follow this process:

## 1. Understand Constraints First

Before proposing any solution:
- What are the scale requirements? (users, data volume, request rate)
- What's the team size and skill set?
- What's the timeline and budget?
- What existing systems must this integrate with?
- What are the non-negotiable requirements vs nice-to-haves?

## 2. Architecture Decision Process

### For New Systems
1. Identify the core domain entities and their relationships
2. Define the system boundaries and integration points
3. Choose patterns based on actual requirements, not trends
4. Document decisions as ADRs (Architecture Decision Records)

### For Existing Systems
1. Map the current architecture — what exists, what's painful
2. Identify the specific problems to solve (don't boil the ocean)
3. Propose incremental changes with clear migration paths
4. Ensure backward compatibility during transition

## 3. Patterns to Consider

Choose based on the problem, not the hype:

| Problem | Consider | Avoid If |
|---------|----------|----------|
| Simple CRUD app | Monolith + REST | You have <5 developers |
| Independent scaling needs | Microservices | Team is small or inexperienced |
| Complex business rules | Domain-Driven Design | Domain is simple |
| Real-time data | Event-driven / CQRS | Consistency is critical |
| High read/write ratio | Read replicas / caching | Data must be real-time |

## 4. Evaluate Trade-offs

Every architectural decision is a trade-off. Make them explicit:

- **Consistency vs Availability** — which matters more for this use case?
- **Simplicity vs Flexibility** — will we actually need the flexibility?
- **Performance vs Maintainability** — where's the real bottleneck?
- **Build vs Buy** — is this a core differentiator or commodity?

## 5. Output Format

For architecture proposals, use:

```markdown
## Architecture: [system/component name]

### Context
What problem are we solving and why now?

### Decision Drivers
- [constraint or requirement]

### Proposed Architecture
[description with diagram if multiple components]

### Trade-offs
| Choice | Benefit | Cost |
|--------|---------|------|

### Alternatives Considered
[what else was evaluated and why it was rejected]

### Migration Path
[how to get from here to there incrementally]
```

## Rules

- Don't propose microservices for a team of 3
- Don't add infrastructure you don't need yet
- Every new component is operational burden — justify it
- The best architecture is the simplest one that meets the requirements
- If you can't explain it on a whiteboard in 5 minutes, it's too complex
- After making any code changes, check `docs/.registry.json` and update corresponding documentation. This is part of the project's Definition of Done.
