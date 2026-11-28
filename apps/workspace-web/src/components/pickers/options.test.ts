// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
import { describe, expect, it } from 'vitest'
import { asText, departmentOptions, userOptions } from './options'

describe('picker options', () => {
  it('maps users with an optional first "none" option', () => {
    const list = userOptions([{ id: 'u1', display_name: 'An' }], 'Chọn người…')
    expect(list.map((o) => o.value)).toEqual(['', 'u1'])
    expect(list[0]!.kind).toBe('special')
    expect(list[1]).toMatchObject({ label: 'An', kind: 'user', userId: 'u1' })
    expect(userOptions([{ id: 'u1', display_name: 'An' }])).toHaveLength(1)
  })
  it('maps departments to dept options keeping raw ids', () => {
    const list = departmentOptions([{ id: 'd1', name: 'Kế toán' }], '—')
    expect(list.map((o) => o.value)).toEqual(['', 'd1'])
    expect(list[1]!.kind).toBe('dept')
  })
  it('asText normalises emitted values', () => {
    expect(asText('a')).toBe('a')
    expect(asText(['b'])).toBe('b')
    expect(asText([])).toBe('')
  })
})
