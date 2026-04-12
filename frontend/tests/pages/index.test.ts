import { describe, it, expect } from 'vitest'

describe('pages/index.vue', () => {
  it('exports a valid component', async () => {
    const mod = await import('~/pages/index.vue')
    expect(mod.default).toBeDefined()
  })
})
