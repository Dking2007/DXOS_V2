// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
import { describe, expect, it } from 'vitest'
import { avatarHue, initials, isLong, linkify, relativeTime } from './text'

describe('relativeTime', () => {
  const now = new Date('2026-10-23T15:00:00')
  it('reads like a person would say it', () => {
    expect(relativeTime('2026-10-23T14:59:30', now)).toBe('Vừa xong')
    expect(relativeTime('2026-10-23T14:35:00', now)).toBe('25 phút trước')
    expect(relativeTime('2026-10-23T09:00:00', now)).toBe('6 giờ trước')
    expect(relativeTime('2026-10-22T20:15:00', now)).toMatch(/^Hôm qua lúc 20:15$/)
    expect(relativeTime('2025-03-02T08:00:00', now)).toBe('02/03/2025')
  })
})

describe('linkify', () => {
  it('turns only http(s) addresses into links and leaves punctuation outside', () => {
    expect(linkify('Xem https://dxos.vn/lich. Cảm ơn!')).toEqual([
      { text: 'Xem ' },
      { text: 'https://dxos.vn/lich', href: 'https://dxos.vn/lich' },
      { text: '. Cảm ơn!' },
    ])
    expect(linkify('javascript:alert(1) <b>x</b>')).toEqual([{ text: 'javascript:alert(1) <b>x</b>' }])
  })
})

describe('people and length', () => {
  it('gives stable initials and colours', () => {
    expect(initials('Nguyễn Văn An')).toBe('VA')
    expect(avatarHue('Trần Thị Bình')).toBe(avatarHue('Trần Thị Bình'))
    expect(avatarHue('Trần Thị Bình')).toBeLessThan(360)
  })
  it('collapses long posts', () => {
    expect(isLong('ngắn')).toBe(false)
    expect(isLong('x'.repeat(500))).toBe(true)
    expect(isLong('a\n'.repeat(9))).toBe(true)
  })
})
