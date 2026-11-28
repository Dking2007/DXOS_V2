// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
import { describe, expect, it } from 'vitest'
import { initials, stampOf, tilt } from './taskPaper'

describe('tasks as sheets of paper', () => {
  it('leans each sheet a little, the same way every time', () => {
    const ids = Array.from({ length: 200 }, (_, i) => `task-${i}-${i * 7919}`)
    for (const id of ids) {
      expect(Math.abs(tilt(id))).toBeLessThanOrEqual(1.2)
      expect(tilt(id)).toBe(tilt(id))
    }
    expect(new Set(ids.map(tilt)).size).toBeGreaterThan(5)
  })
  it('shows who holds it by initials', () => {
    expect(initials('Nguyễn Thị Lan')).toBe('NL')
    expect(initials('  đông ')).toBe('Đ')
    expect(initials('')).toBe('?')
  })
  it('stamps closed work before overdue work', () => {
    expect(stampOf({ status: 'completed', overdue: true })?.label).toBe('Hoàn tất')
    expect(stampOf({ status: 'cancelled', overdue: false })?.tone).toBe('grey')
    expect(stampOf({ status: 'in_progress', overdue: true })).toEqual({ label: 'Quá hạn', tone: 'red' })
    expect(stampOf({ status: 'returned', overdue: false })?.tone).toBe('amber')
    expect(stampOf({ status: 'in_progress', overdue: false })).toBeNull()
  })
})
