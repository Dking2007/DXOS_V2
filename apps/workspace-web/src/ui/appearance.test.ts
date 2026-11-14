// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
import { describe, expect, it } from 'vitest'
import { CONTRAST_PAIRS, DEFAULT_COLORS, colorCss, contrast, contrastReport, term } from './appearance'
import { visibleGroups } from './nav'
// The server checks the same colours; both sides must agree on the stock palette and the pairs.
import packs from '../../../../services/workspace-api/src/dx_workspace/packs.py?raw'

describe('sector pack appearance', () => {
  it('uses the same stock colours and contrast pairs as the server', () => {
    for (const theme of ['light', 'dark'] as const) {
      const start = packs.indexOf(`"${theme}": {`, packs.indexOf('DEFAULT_COLORS = {'))
      const block = packs.slice(start, packs.indexOf('}', start))
      const server = Object.fromEntries([...block.matchAll(/"([a-z0-9-]+)": "(#[0-9a-f]{6})"/g)].map((m) => [m[1], m[2]]))
      expect(server).toEqual(DEFAULT_COLORS[theme])
    }
    const pairs = [...packs.matchAll(/\("([a-z0-9-]+)", "([a-z0-9-]+)", "([^"]+)"\)/g)].map((m) => [m[1], m[2], m[3]])
    expect(pairs).toEqual(CONTRAST_PAIRS)
  })

  it('reads stock colours as readable and flags a pale main colour', () => {
    expect(contrastReport(undefined).every((item) => item.ok)).toBe(true)
    expect(contrast('#ffffff', '#000000')).toBeCloseTo(21, 0)
    const pale = contrastReport({ light: { teal: '#9cc7f0' } })
    expect(pale.filter((item) => !item.ok).map((item) => item.label)).toEqual(['Chữ trên nút chính'])
  })

  it('writes light colours on :root and dark ones for both ways of choosing dark', () => {
    const css = colorCss({ light: { teal: '#1d5c96' }, dark: { teal: '#7fb6ef' } })
    expect(css).toContain(':root { --teal: #1d5c96; }')
    expect(css).toContain(":root[data-theme='dark'] { --teal: #7fb6ef; }")
    expect(css).toContain(":root:not([data-theme='light']) { --teal: #7fb6ef; }")
    // Anything that is not a colour variable with a hex value is dropped.
    expect(colorCss({ light: { 'teal;}body{': '#000000', navy: 'red' } })).toBe('')
  })

  it('swaps words, capitalised or not, longest first and only once', () => {
    const terms = { 'Hồ sơ': 'Hồ sơ học vụ', 'Hồ sơ gần đây': 'Hồ sơ vừa mở', 'Phòng ban': 'Tổ chuyên môn' }
    expect(term('Hồ sơ', terms)).toBe('Hồ sơ học vụ')
    expect(term('Lập hồ sơ trình duyệt', terms)).toBe('Lập hồ sơ học vụ trình duyệt')
    expect(term('Hồ sơ gần đây', terms)).toBe('Hồ sơ vừa mở')
    expect(term('Chọn phòng ban', terms)).toBe('Chọn tổ chuyên môn')
    expect(term('Công việc', undefined)).toBe('Công việc')
  })

  it('hides and orders menu modules and renames them, never hiding what is not allowed by the server', () => {
    const groups = visibleGroups(
      () => true,
      { hide: ['feed'], order: ['cases', 'tasks'] },
      { 'Hồ sơ': 'Hồ sơ học vụ' },
    )
    const work = groups[0]!.links.map((link) => link.key)
    expect(work.slice(0, 2)).toEqual(['cases', 'tasks'])
    expect(work).not.toContain('feed')
    expect(groups[0]!.links[0]!.label).toBe('Hồ sơ học vụ')
    // Administration keeps the packs screen for those who may manage the organisation.
    expect(groups.flatMap((group) => group.links.map((link) => link.key))).toContain('packs')
    expect(visibleGroups(() => false).flatMap((group) => group.links.map((link) => link.key))).not.toContain('packs')
  })
})
