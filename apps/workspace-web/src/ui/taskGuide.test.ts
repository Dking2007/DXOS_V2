// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
import { describe, expect, it } from 'vitest'
import { dueText, nextStep, taskStage } from './taskGuide'

describe('task guide', () => {
  it('places each status on the way to done', () => {
    expect(taskStage('assigned')).toBe(0)
    expect(taskStage('returned')).toBe(2)
    expect(taskStage('submitted')).toBe(3)
    expect(taskStage('completed')).toBe(4)
    expect(taskStage('cancelled')).toBe(-1)
  })

  it('says how long is left or how late it is', () => {
    const now = Date.parse('2026-11-09T08:00:00Z')
    expect(dueText('2026-11-11T08:00:00Z', 'in_progress', now)).toBe('Còn 2 ngày')
    expect(dueText('2026-11-09T05:00:00Z', 'in_progress', now)).toBe('Quá hạn 3 giờ')
    expect(dueText('2026-11-01T00:00:00Z', 'completed', now)).toBe('')
    expect(dueText(null, 'in_progress', now)).toBe('')
  })

  it('tells each person their next step', () => {
    const base = { hasAssignee: true, canManage: false, isAssignee: true }
    expect(nextStep({ ...base, status: 'assigned' }).text).toContain('Tiếp nhận')
    expect(nextStep({ ...base, status: 'in_progress', requiredFiles: 2, fileCount: 1 }).text).toContain('2 tệp')
    expect(nextStep({ ...base, status: 'returned', reason: 'Thiếu số liệu' }).text).toContain('Thiếu số liệu')
    const manager = { hasAssignee: true, canManage: true, isAssignee: false }
    expect(nextStep({ ...manager, status: 'submitted' })).toMatchObject({ tone: 'warn' })
    expect(nextStep({ ...manager, status: 'submitted' }).text).toContain('Nghiệm thu')
    expect(nextStep({ ...manager, status: 'in_progress', overdue: true }).text).toContain('đổi hạn')
    expect(nextStep({ ...base, hasAssignee: false, status: 'assigned' }).text).toContain('trưởng đơn vị')
  })
})
