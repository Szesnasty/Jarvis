# Step 28b — Memory Document Grouping

> **Goal**: In the Memory sidebar, render every document that was
> split into sections as one collapsible row (file title + section
> count). Singleton notes stay flat. After ingesting four 100-page
> PDFs the sidebar shows 4 rows by default, not 50.

**Parent**: [step-28-document-intelligence.md](step-28-document-intelligence.md)
**Status**: ⬜ Planned

---

## Why

Step 27a already produces the right shape on disk. For a PDF
`hai-ai-index-report-2025.pdf` ingested to `knowledge/`:

```
memory/knowledge/hai-ai-index-report-2025/
  index.md              # frontmatter: document_type: pdf-document
  01-front-matter.md    # frontmatter: parent: …/index.md, section_index: 1
  02-introduction.md    # frontmatter: parent: …/index.md, section_index: 2
  …
```

But the sidebar in
[NoteList.vue:54-79](../../frontend/app/components/NoteList.vue#L54-L79)
treats every note as a flat row, because `NoteMetadata` in
[types/index.ts:21-28](../../frontend/app/types/index.ts#L21-L28)
only carries `path / title / folder / tags / updated_at /
word_count`. The grouping signal exists in frontmatter but is never
read on listing.

---

## Design

### Backend — expose three frontmatter fields on listing

[memory_service.py:186](../../backend/services/memory_service.py#L186)
selects from the `notes` table. The `frontmatter` column already
stores raw JSON (see write paths at lines 325-331 and 368-377). Two
options:

- **Option A (chosen)**: parse the relevant subset out of `frontmatter`
  in `list_notes` and return three new fields on each item.
- Option B: add three indexed columns. Heavier migration, no benefit
  at this scale.

In `list_notes`, after `tags = json.loads(row["tags"])`, also do:

```python
fm_raw = row["frontmatter"] or "{}"
try:
    fm = json.loads(fm_raw)
except (json.JSONDecodeError, TypeError):
    fm = {}
item.update({
    "document_type": fm.get("document_type"),    # "pdf-document" on index notes
    "parent": fm.get("parent"),                  # "<folder>/<slug>/index.md" on sections
    "section_index": fm.get("section_index"),    # int, present on sections
})
```

Add `frontmatter` to the SELECT list at line 186 (and in the
search-path query at line 167).

### Frontend type + composable

In [types/index.ts](../../frontend/app/types/index.ts):

```ts
export interface NoteMetadata {
  path: string
  title: string
  folder: string
  tags: string[]
  updated_at: string
  word_count: number
  document_type?: string | null
  parent?: string | null
  section_index?: number | null
}
```

In [useApi.ts](../../frontend/app/composables/useApi.ts) `fetchNotes`
just passes the new fields through.

### Grouping logic (frontend, pure)

A new composable `useNoteTree.ts` (or a function in the existing
`useApi.ts`) groups a `NoteMetadata[]` into:

```ts
type NoteTreeNode =
  | { kind: 'note'; note: NoteMetadata }
  | { kind: 'document'; index: NoteMetadata; sections: NoteMetadata[] }
```

Algorithm:

1. Scan list once, bucket by `parent` field. Notes with `parent == X`
   go into bucket `X`.
2. For each note where `document_type == 'pdf-document'` (or future
   document types), look up its bucket by its own `path`. Emit a
   `document` node with the index note + sorted sections (by
   `section_index`).
3. Notes that are neither index nor section ⇒ emit `note`.
4. Orphan sections (`parent` set but no matching index in the current
   list — possible when filtering by folder) ⇒ emit as plain `note`.

Sort: documents and singletons interleaved by `updated_at` of the
representative note (index for documents, the note itself otherwise).
This keeps the existing "most recent first" ordering intact.

### Render in NoteList.vue

Replace the current `<li v-for="note in notes">` block with a
`<NoteTreeRow>` per tree node. Document rows show:

```
▸ HAI AI Index Report 2025                        12 sections
  imported, pdf · 2026-04-25
```

Expanded:

```
▾ HAI AI Index Report 2025                        12 sections
  imported, pdf · 2026-04-25
    01 Front Matter
    02 Introduction
    03 Research and Development
    …
```

Click on the document title row ⇒ select `index.md`.
Click on a section row ⇒ select that section.
Delete button on the document row ⇒ confirm dialog says "This will
delete the document and all 12 sections" and calls `deleteNote` for
each path (existing endpoint, no API change).

Expanded state is per-document, persisted in `useState<Record<string,
boolean>>('noteTreeExpanded')` so that switching between Memory and
Graph doesn't collapse everything.

### Search behaviour

When a search query is active:

- If a section matches, **auto-expand** its parent document so the
  match is visible.
- If only the index matches but no sections, render the document as
  a singleton (no expand affordance) to avoid implying matches that
  don't exist.

---

## Code changes

| File | Change |
|------|--------|
| [backend/services/memory_service.py](../../backend/services/memory_service.py) | `list_notes`: add `frontmatter` to SELECT; parse and expose `document_type`, `parent`, `section_index`. |
| [frontend/app/types/index.ts](../../frontend/app/types/index.ts) | Extend `NoteMetadata`. Add `NoteTreeNode` union. |
| `frontend/app/composables/useNoteTree.ts` (new) | Pure tree builder. |
| [frontend/app/components/NoteList.vue](../../frontend/app/components/NoteList.vue) | Replace flat list with tree rendering; expansion state via `useState`. |
| `frontend/app/components/NoteTreeRow.vue` (new) | Single row component (document or note variant). |

No new endpoints, no schema changes.

---

## Tests

- `backend/tests/test_list_notes_frontmatter.py`:
  1. `test_list_notes_exposes_document_type` — write an index note
     with `document_type: pdf-document`, list returns the field.
  2. `test_list_notes_exposes_parent_and_section_index` — write a
     section note with both, list returns both.
  3. `test_list_notes_missing_fields_default_to_none` — plain note
     has all three fields = None.
- `frontend/test/composables/useNoteTree.test.ts`:
  1. Builds a 1-document + 3-section + 5-singleton tree correctly.
  2. Orphan sections (parent missing from input) fall through to
     plain notes.
  3. Sort order respects `updated_at` of the document's index.

---

## Acceptance

- Re-ingesting the four reference PDFs and opening Memory shows
  exactly 4 collapsible rows for them, plus the user's existing
  notes flat. No section row visible until a document is expanded.
- Searching for a term that appears in a section auto-expands its
  parent document.
- Deleting a document row removes the index note and every section
  note in one confirm.

---

## Out of scope

- Server-side grouping (kept client-side; same payload shape works
  for Graph page where flat list is still right).
- Drag-to-reorder sections.
- Editing the document's section structure from the UI.
- Other grouping triggers besides `document_type: pdf-document` —
  Step 28d may add more, but the union type already accommodates them.
