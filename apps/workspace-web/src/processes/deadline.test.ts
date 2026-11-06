// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
import { describe, expect, it } from 'vitest'
import { deadlineParts, deadlineText } from './deadline'

describe('step deadline', () => {
  it('reads whole days as days and anything else as hours', () => {
    expect(deadlineParts(48)).toEqual({ amount: 2, unit: 24 })
    expect(deadlineParts(36)).toEqual({ amount: 36, unit: 1 })
    expect(deadlineParts(null)).toEqual({ amount: 0, unit: 24 })
    expect(deadlineText(24)).toBe('Trong 1 ngày')
    expect(deadlineText(4)).toBe('Trong 4 giờ')
    expect(deadlineText(undefined)).toBe('Không giới hạn thời gian')
  })
})
