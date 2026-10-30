// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
import { describe, expect, it } from 'vitest'
import { parseInline, parseMarkdown } from './markdown'

describe('assistant markdown', () => {
  it('reads paragraphs, numbered steps, bullets and headings', () => {
    const blocks = parseMarkdown('## Các bước\n1. Mở **Hồ sơ** [1]\n2. Bấm `Tạo hồ sơ`\n\n- Lưu ý\n- Hết\n\nXong.')
    expect(blocks.map((b) => b.t)).toEqual(['h', 'ol', 'ul', 'p'])
    const steps = blocks[1] as { t: 'ol'; items: unknown[][] }
    expect(steps.items).toHaveLength(2)
    expect(steps.items[0]).toEqual([
      { t: 'text', v: 'Mở ' },
      { t: 'bold', v: 'Hồ sơ' },
      { t: 'text', v: ' ' },
      { t: 'cite', n: 1 },
    ])
  })

  it('never turns text into markup', () => {
    const inline = parseInline('<img src=x onerror=alert(1)> javascript:alert(1)')
    expect(inline).toEqual([{ t: 'text', v: '<img src=x onerror=alert(1)> javascript:alert(1)' }])
  })

  it('keeps links to http(s) only and leaves trailing punctuation out', () => {
    expect(parseInline('Xem https://dxos.vn/huong-dan.')).toEqual([
      { t: 'text', v: 'Xem ' },
      { t: 'link', v: 'https://dxos.vn/huong-dan', href: 'https://dxos.vn/huong-dan' },
      { t: 'text', v: '.' },
    ])
  })

  it('keeps code blocks as they are', () => {
    expect(parseMarkdown('```\na **b**\n```')).toEqual([{ t: 'code', v: 'a **b**' }])
  })
})
