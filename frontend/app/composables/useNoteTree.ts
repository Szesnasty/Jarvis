import type { NoteMetadata, NoteTreeNode } from '~/types'

/**
 * Step 28b — group a flat list of notes into a tree where split documents
 * (PDF section split, future text/json splits) collapse into one expandable
 * parent row and singleton notes stay flat.
 *
 * The grouping signal lives entirely in frontmatter:
 *   - Index notes have `document_type: pdf-document` (or another known type)
 *   - Section notes have `parent: <index-path>` and `section_index: N`
 *
 * Sort order: documents and singletons interleave by `updated_at` DESC of
 * the representative note (the index note for documents, the note itself
 * otherwise) so the existing "most recent first" behaviour is preserved.
 *
 * Pure function — no I/O, no Vue reactivity. Easy to unit-test.
 */

const DOCUMENT_TYPES = new Set(['pdf-document'])

function isDocumentIndex(note: NoteMetadata): boolean {
  return !!note.document_type && DOCUMENT_TYPES.has(note.document_type)
}

function isSection(note: NoteMetadata): boolean {
  return !!note.parent
}

export function buildNoteTree(notes: NoteMetadata[]): NoteTreeNode[] {
  if (!notes.length) return []

  // Bucket sections by their parent path so we can attach them to the index
  // in one pass without quadratic scans.
  const sectionsByParent = new Map<string, NoteMetadata[]>()
  const indexByPath = new Map<string, NoteMetadata>()

  for (const n of notes) {
    if (isDocumentIndex(n)) {
      indexByPath.set(n.path, n)
    }
    if (isSection(n) && n.parent) {
      const bucket = sectionsByParent.get(n.parent)
      if (bucket) bucket.push(n)
      else sectionsByParent.set(n.parent, [n])
    }
  }

  // Sort each section bucket by section_index (fallback to title) so the
  // tree shows sections in document order regardless of input order.
  for (const bucket of sectionsByParent.values()) {
    bucket.sort((a, b) => {
      const ai = a.section_index ?? Number.MAX_SAFE_INTEGER
      const bi = b.section_index ?? Number.MAX_SAFE_INTEGER
      if (ai !== bi) return ai - bi
      return (a.title || a.path).localeCompare(b.title || b.path)
    })
  }

  const consumed = new Set<string>()
  const out: NoteTreeNode[] = []

  for (const n of notes) {
    if (consumed.has(n.path)) continue

    if (isDocumentIndex(n)) {
      const sections = sectionsByParent.get(n.path) || []
      // Mark the index + every section as consumed so they are not also
      // emitted as plain notes later.
      consumed.add(n.path)
      for (const s of sections) consumed.add(s.path)
      out.push({ kind: 'document', index: n, sections })
      continue
    }

    if (isSection(n) && n.parent && indexByPath.has(n.parent)) {
      // Belongs to a document we either already emitted or will emit when
      // we hit the index. Skip — the document node owns it.
      consumed.add(n.path)
      continue
    }

    // Either a plain note, or an orphan section whose index is not in the
    // current list (e.g. filtered out by folder). Render flat.
    consumed.add(n.path)
    out.push({ kind: 'note', note: n })
  }

  return out
}

/**
 * Sort a built tree by the representative note's `updated_at` DESC. Kept as
 * a separate step so callers (search, filtered views) can opt out and
 * preserve the input order if they computed a different ranking upstream.
 */
export function sortNoteTreeByRecency(tree: NoteTreeNode[]): NoteTreeNode[] {
  return [...tree].sort((a, b) => {
    const aTs = a.kind === 'document' ? a.index.updated_at : a.note.updated_at
    const bTs = b.kind === 'document' ? b.index.updated_at : b.note.updated_at
    return bTs.localeCompare(aTs)
  })
}
