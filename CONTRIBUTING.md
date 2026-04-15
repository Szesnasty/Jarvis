# Contributing to Jarvis

Thanks for your interest in contributing!

## Getting started

1. Fork the repo and clone it
2. Run `npm run wake-up-jarvis` to set everything up
3. Use `npm run dev` for development (HMR frontend + auto-reload backend)

## Strong areas for contribution

- **Retrieval quality** — BM25 tuning, semantic search improvements, graph scoring
- **Graph UX** — visualization, interaction, layout algorithms
- **Specialist templates** — pre-built specialist configs for common use cases
- **Ingest pipelines** — new file formats, smarter parsing, better chunking
- **Local model support** — Ollama, llama.cpp, other local LLM integrations
- **Obsidian workflows** — better vault compatibility, sync patterns
- **Onboarding polish** — first-run experience, error messages, docs

## Pull requests

- Keep PRs focused — one feature or fix per PR
- Include a clear description of what changed and why
- Add tests for new backend functionality
- Make sure existing tests pass: `cd backend && python -m pytest`

## Code style

- **Backend**: Python 3.12+, type hints, async where appropriate
- **Frontend**: TypeScript strict mode, Vue 3 Composition API
- No need to add docstrings to code you didn't change

## Reporting bugs

Open an issue with:
- Steps to reproduce
- Expected vs actual behavior
- OS and Python/Node versions

## Questions?

Open a discussion or issue. We're happy to help.
