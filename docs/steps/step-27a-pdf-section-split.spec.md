# Step 27a — Split Large PDFs into Section Notes at Ingest

> **Goal**: When a PDF exceeds a size threshold, split it into one
> Markdown note per top-level section, plus an index note that links
> them. The graph then sees the PDF as a *cluster of related notes*
> instead of a single hub, unlocking real edges between sections.

**Parent**: [step-27-graph-density.md](step-27-graph-density.md)
**Status**: ⬜ Planned

---

## Design

### Trigger

Apply section split only when **all** of the following hold for a PDF:

- Extracted text length ≥ `SECTION_SPLIT_MIN_CHARS = 30_000`
  (~10–15 pages of dense text).
- At least 4 detected top-level headings (see "Heading detection").
- File extension is `.pdf`. Other formats unchanged in this step.

Below the threshold the existing single-file behaviour is preserved
verbatim — no regression for memos, emails, short notes.

### Heading detection

PDF text extraction does not preserve Markdown structure, so we run a
lightweight heuristic over the extracted plain text:

1. Split on lines.
2. A line is a **section heading candidate** when:
   - Length between 4 and 120 characters.
   - Surrounded by blank lines (or file start/end).
   - Matches one of:
     - Numbered heading: `^\d+(\.\d+)*\s+[A-Z\p{L}]`
       (e.g. `1 Introduction`, `2.3 Threat Model`).
     - All-caps heading: `^[A-Z][A-Z0-9 \-:&]{3,}$`
       (e.g. `ABSTRACT`, `RELATED WORK`).
     - Title-case heading on its own line, no trailing period:
       `^[A-Z][\w\- ,&:]{3,}$` and word count ≤ 12.
3. Top-level vs sub-level: numbered headings with one dot or no dot are
   top-level; deeper numbering or shorter all-caps lines (≤ 25 chars)
   roll up under their nearest top-level heading.
4. Always include an implicit `Front Matter` section for any text
   before the first detected heading.

If fewer than 4 top-level headings are detected, fall through to the
existing single-file path (do not split).

### Output layout

For input file `hai-ai-index-report-2025.pdf` going to `knowledge/`:

```
memory/knowledge/hai-ai-index-report-2025/
  index.md                 # overview note, links to all sections
  01-front-matter.md
  02-introduction.md
  03-research-and-development.md
  ...
  NN-conclusion.md
```

- The folder name is the slug of the original filename (reuse existing
  `_slugify`).
- Each section file has frontmatter:
  ```yaml
  ---
  title: <section heading verbatim>
  date: <today>
  source: <original PDF path>
  parent: knowledge/hai-ai-index-report-2025/index.md
  section_index: 3
  tags: [imported, pdf, section]
  ---
  ```
- `index.md` frontmatter:
  ```yaml
  ---
  title: <PDF stem, humanised>
  date: <today>
  source: <original PDF path>
  tags: [imported, pdf, document]
  document_type: pdf-document
  ---
  ```
  Body: a numbered list of `[[hai-ai-index-report-2025/03-research-and-development]]`
  wiki-links, one per section, in document order. The bidirectional
  link resolver in `graph_service/builder.py::_resolve_bidirectional_links`
  then automatically adds reverse edges from each section back to the
  index.

### Graph effect (free wins)

- Single `note:` hub becomes `1 + N` `note:` nodes.
- `linked` edges between index ↔ each section (forward + reverse).
- `part_of` edges from each section to its `area:knowledge/...` folder.
- Entity extraction runs **per section**, so each section gets its own
  entity satellites — but entities shared across sections (the same
  author/org appearing in introduction and methods) collapse to single
  shared nodes, naturally forming bridges between section notes.
- Concept pass (Step 27c) sees N documents instead of 1 → real TF-IDF
  signal across sections of the same paper.

### Code changes

All in `backend/services/ingest.py`. No graph or schema changes.

1. **New module-level constants**:
   ```python
   SECTION_SPLIT_MIN_CHARS = 30_000
   SECTION_SPLIT_MIN_HEADINGS = 4
   ```

2. **New helper `_detect_pdf_sections(text: str) -> list[Section]`**
   returning a list of `(title, body)` tuples in document order, with
   the front-matter section first if non-empty. Pure, no I/O,
   unit-testable.

3. **New helper `_emit_pdf_sections(...)`** that:
   - Creates `folder / slug(title)` directory (re-uses `_unique_path`
     if it already exists).
   - Writes `index.md` and each `NN-slug.md` file with frontmatter.
   - Calls `index_note_file` for each new file (ordering: index first,
     then sections — so sections can reference the index).
   - Calls `connect_note` once on the index after all sections are
     indexed (sections inherit the connection chain via the wiki-link
     graph; per-section Smart Connect would be expensive and
     redundant).
   - Returns a single result dict matching the existing shape, with
     `sections: int` added.

4. **Branch in `fast_ingest`** for `.pdf`:
   ```python
   _stage("extracting")
   text = await asyncio.to_thread(_extract_pdf_text, file_path)
   sections = _detect_pdf_sections(text)
   if (
       len(text) >= SECTION_SPLIT_MIN_CHARS
       and len(sections) >= SECTION_SPLIT_MIN_HEADINGS
   ):
       _stage("splitting")
       return await _emit_pdf_sections(...)
   # else: existing single-file behaviour (unchanged)
   ```

5. **Logging**: one INFO line per PDF that gets split, with N sections
   and total chars. Helps diagnose ingest behaviour without DEBUG.

### Idempotence

Re-ingesting the same PDF must not duplicate sections. Strategy:

- The folder name is deterministic (slug of filename stem).
- `_unique_path` already adds numeric suffixes; for the *folder* path
  we apply the same logic. Result: re-ingesting `report.pdf` after the
  first time creates `report-1/` (matches existing single-file
  behaviour for `.md` re-ingest).

### Tests

Add `backend/tests/test_pdf_section_split.py`:

1. `test_detect_sections_numbered_headings` — synthetic text with
   `1 Intro\n\n...` style headings produces correct sections.
2. `test_detect_sections_all_caps` — `ABSTRACT\n\n...` style works.
3. `test_detect_sections_below_threshold` — short text returns < 4
   sections, falls back to single-file.
4. `test_emit_sections_writes_index_and_files` — uses tmp workspace,
   asserts file layout and frontmatter `parent`/`section_index`.
5. `test_pdf_split_reingest_idempotent` — second ingest writes to
   suffixed folder, no overwrite.
6. `test_short_pdf_uses_single_file_path` — small PDF still produces
   one file, no folder.

### Acceptance

- Re-ingesting the four reference PDFs produces ≥ 5 section notes per
  PDF and at least one shared `concept:` bridge between two different
  PDFs that were previously unconnected.
- All new and existing tests under `backend/tests/` pass.
- No change in behaviour for `.md`, `.txt`, `.json`, `.csv`, `.xml`,
  or for PDFs below the threshold.

### Out of scope

- Splitting `.txt` or `.md` imports.
- Joining sections back into a single retrieval unit (chunking already
  handles cross-section retrieval via the existing chunk pipeline).
- Detecting sub-sub-sections (only top-level headings drive splits).
