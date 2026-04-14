---
paths: ["./**/*.js","./**/*.jsx"]
description: Enforces automatic documentation when source files are created or modified
---

## Automatic documentation — no manual step required

When you create or modify ANY source file, documentation MUST be handled as part of the same task. Do not ask the user whether to document — just do it. Do not defer to a skill or separate step.

### For every source file you touch:

1. Read `docs/.registry.json`
2. Find the file path in any feature's `sources` array

**If the file IS in the registry:**
- Read the corresponding doc file
- Update any sections that no longer match your changes (Summary, How It Works, Key Files, API/Interface)
- Set `last_updated` to today in both the doc frontmatter and the registry entry
- If your change affects the public interface (exported functions, types, or behavior), set dependent features' status to `"stale"` via the `depends_on` field

**If the file is NOT in the registry** and contains significant logic (not just types, configs, or one-line re-exports):
- Determine the feature name from the file's purpose (kebab-case)
- Create `docs/features/{feature-name}.md` with sections: Summary, How It Works, Key Files, and optionally API/Interface and Gotchas
- Add the mapping to `docs/.registry.json`:
  ```json
  "feature-name": {
    "doc": "docs/features/feature-name.md",
    "sources": ["src/path/to/file.ts"],
    "status": "current",
    "last_updated": "YYYY-MM-DD",
    "depends_on": []
  }
  ```
- Populate `depends_on` based on imports from other registered features

**If the registry has entries with `status: "needs-review"`**, fill them in when you encounter them.

### Plan → Implement → Document is ONE action

When you plan a feature (create an ADR, design doc, or implementation plan) and the user asks you to implement it, the implementation is not done until:
1. Code is written and works
2. New source files are registered in `docs/.registry.json`
3. Feature docs are created or updated
4. `last_updated` is set on all touched docs

Do not stop after writing code and ask whether to document. The documentation is part of writing the code.
