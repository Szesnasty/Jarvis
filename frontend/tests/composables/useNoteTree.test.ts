import { describe, it, expect } from 'vitest'
import type { NoteMetadata } from '~/types'
import { buildNoteTree, sortNoteTreeByRecency } from '~/composables/useNoteTree'

function note(p: Partial<NoteMetadata>): NoteMetadata {
  return {
    path: p.path ?? 'inbox/x.md',
    title: p.title ?? p.path ?? 'Untitled',
    folder: p.folder ?? 'inbox',
    tags: p.tags ?? [],
    updated_at: p.updated_at ?? '2026-04-25T10:00:00Z',
    word_count: p.word_count ?? 100,
    document_type: p.document_type ?? null,
    parent: p.parent ?? null,
    section_index: p.section_index ?? null,
  }
}

describe('buildNoteTree', () => {
  it('returns empty array for empty input', () => {
    expect(buildNoteTree([])).toEqual([])
  })

  it('keeps singleton notes flat', () => {
    const tree = buildNoteTree([
      note({ path: 'inbox/a.md', title: 'A' }),
      note({ path: 'inbox/b.md', title: 'B' }),
    ])
    expect(tree).toHaveLength(2)
    expect(tree.every(n => n.kind === 'note')).toBe(true)
  })

  it('groups index + sections into one document node', () => {
    const tree = buildNoteTree([
      note({ path: 'k/doc/index.md', title: 'Doc', document_type: 'pdf-document' }),
      note({ path: 'k/doc/01-intro.md', title: 'Intro', parent: 'k/doc/index.md', section_index: 1 }),
      note({ path: 'k/doc/02-methods.md', title: 'Methods', parent: 'k/doc/index.md', section_index: 2 }),
      note({ path: 'inbox/plain.md', title: 'Plain' }),
    ])

    expect(tree).toHaveLength(2)
    const doc = tree.find(n => n.kind === 'document')
    expect(doc).toBeDefined()
    if (doc?.kind === 'document') {
      expect(doc.index.path).toBe('k/doc/index.md')
      expect(doc.sections).toHaveLength(2)
      expect(doc.sections[0]!.path).toBe('k/doc/01-intro.md')
      expect(doc.sections[1]!.path).toBe('k/doc/02-methods.md')
    }
    const plain = tree.find(n => n.kind === 'note')
    expect(plain).toBeDefined()
  })

  it('sorts sections by section_index regardless of input order', () => {
    const tree = buildNoteTree([
      note({ path: 'd/index.md', title: 'D', document_type: 'pdf-document' }),
      note({ path: 'd/03-c.md', parent: 'd/index.md', section_index: 3 }),
      note({ path: 'd/01-a.md', parent: 'd/index.md', section_index: 1 }),
      note({ path: 'd/02-b.md', parent: 'd/index.md', section_index: 2 }),
    ])
    const doc = tree[0]
    expect(doc?.kind).toBe('document')
    if (doc?.kind === 'document') {
      const order = doc.sections.map(s => s.section_index)
      expect(order).toEqual([1, 2, 3])
    }
  })

  it('treats orphan sections (parent not in input) as plain notes', () => {
    const tree = buildNoteTree([
      note({ path: 'd/03-orphan.md', parent: 'd/index.md', section_index: 3 }),
      note({ path: 'inbox/x.md' }),
    ])
    expect(tree).toHaveLength(2)
    expect(tree.every(n => n.kind === 'note')).toBe(true)
  })

  it('does not emit a section twice when it appears before the index', () => {
    const tree = buildNoteTree([
      note({ path: 'd/01-intro.md', parent: 'd/index.md', section_index: 1 }),
      note({ path: 'd/index.md', document_type: 'pdf-document' }),
    ])
    expect(tree).toHaveLength(1)
    const doc = tree[0]
    expect(doc?.kind).toBe('document')
    if (doc?.kind === 'document') {
      expect(doc.sections).toHaveLength(1)
    }
  })

  it('document_type values outside the known set fall through to flat note', () => {
    const tree = buildNoteTree([
      note({ path: 'k/odd.md', document_type: 'mystery-type' }),
    ])
    expect(tree).toHaveLength(1)
    expect(tree[0]?.kind).toBe('note')
  })
})

describe('sortNoteTreeByRecency', () => {
  it('orders documents and singletons by representative updated_at DESC', () => {
    const sorted = sortNoteTreeByRecency([
      { kind: 'note', note: note({ path: 'a.md', updated_at: '2026-04-20T00:00:00Z' }) },
      { kind: 'document', index: note({ path: 'd/index.md', document_type: 'pdf-document', updated_at: '2026-04-25T00:00:00Z' }), sections: [] },
      { kind: 'note', note: note({ path: 'b.md', updated_at: '2026-04-22T00:00:00Z' }) },
    ])

    const repPaths = sorted.map(n => n.kind === 'document' ? n.index.path : n.note.path)
    expect(repPaths).toEqual(['d/index.md', 'b.md', 'a.md'])
  })
})
