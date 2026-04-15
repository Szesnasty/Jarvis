# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| latest  | Yes       |

## Reporting a vulnerability

If you discover a security vulnerability, please report it responsibly.

**Do not open a public issue.**

Instead, email **security@jarvis-app.dev** or use [GitHub Security Advisories](https://github.com/Szesnasty/Jarvis/security/advisories/new) to report it privately.

You should receive a response within 48 hours. We will work with you to understand the issue and coordinate a fix before any public disclosure.

## Scope

Jarvis runs locally on your machine. Security concerns include:

- **API key handling** — keys are stored in your browser's local storage and sent only to the backend over localhost
- **Path traversal** — all file operations are restricted to the workspace directory
- **Input validation** — user input is sanitized before use in file paths, queries, and API calls
- **WebSocket security** — connections are local-only by default

## Out of scope

- Vulnerabilities in third-party dependencies (report upstream)
- Issues requiring physical access to the user's machine
- Social engineering attacks
