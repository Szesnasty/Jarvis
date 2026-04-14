---
name: senior-backend
description: >
  Build robust backend systems. Use when designing APIs, writing backend logic,
  optimizing database queries, implementing authentication, handling errors,
  or reviewing backend code. Covers Node.js, Express, Go, Python, PostgreSQL,
  GraphQL, and REST APIs.
---

# Backend Development

## API Design

### REST Endpoints
- Use nouns for resources, HTTP verbs for actions: `GET /users/:id` not `GET /getUser`
- Return appropriate status codes: 201 for creation, 204 for deletion, 404 for missing
- Use consistent error response format across all endpoints
- Version APIs when breaking changes are unavoidable: `/api/v2/`
- Paginate list endpoints from day one — don't add it after hitting limits

### GraphQL
- Keep resolvers thin — business logic belongs in service layer
- Use DataLoader for N+1 query prevention
- Define clear input types for mutations
- Implement depth/complexity limiting for public APIs

## Database

### Query Patterns
- Always add indexes for fields used in WHERE, JOIN, and ORDER BY
- Use parameterized queries — never string interpolation for SQL
- Prefer specific column selection over `SELECT *`
- Add `LIMIT` to queries that could return unbounded results
- Use transactions for multi-step writes that must be atomic

### Schema Design
- Normalize until it hurts performance, then denormalize strategically
- Add `created_at` and `updated_at` timestamps to every table
- Use UUIDs for public-facing IDs, auto-increment for internal references
- Define foreign key constraints — let the database enforce integrity

## Error Handling

- Catch errors at service boundaries, not deep in business logic
- Log the full error internally, return safe messages to clients
- Use typed errors with error codes clients can switch on
- Don't swallow errors — if you catch it, either handle it or re-throw it
- Implement graceful degradation for non-critical external dependencies

## Authentication & Authorization

- Hash passwords with bcrypt/argon2 — never SHA/MD5
- Use short-lived JWTs (15 min) with refresh token rotation
- Validate authorization on every request, not just at the gateway
- Rate limit auth endpoints aggressively (login, signup, password reset)
- Never expose internal user IDs in tokens — use opaque session references

## Performance

- Measure before optimizing — profile, don't guess
- Cache at the right layer: HTTP cache > application cache > query cache
- Use connection pooling for database connections
- Make external API calls async/non-blocking when possible
- Set timeouts on all external calls — no unbounded waits

## Rules

- Validate all input at system boundaries
- Never trust client-side validation alone
- Log structured data (JSON), not strings
- Keep controllers thin — orchestration only, no business logic
- Write integration tests for critical paths, unit tests for business logic
- After making any code changes, check `docs/.registry.json` and update corresponding documentation. This is part of the project's Definition of Done.
