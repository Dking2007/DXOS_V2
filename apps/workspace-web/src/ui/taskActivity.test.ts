// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
import { describe, expect, it } from 'vitest'
import { activitySteps, canvasLayout, stepsPerRow, toStep } from './taskActivity'

const ev = (
  action: string,
  detail: Record<string, unknown> = {},
  id = action,
) => ({
  id,
  action,
  actor_name: 'Lan',
  detail,
  created_at: '2026-11-20T08:00:00Z',
})

describe('task activity as a workflow', () => {
  it('gives main steps a tone and keeps the reason', () => {
    const step = toStep(ev('return', { reason: 'Thiếu chữ ký' }))
    expect(step).toMatchObject({
      label: 'Trả lại',
      tone: 'warn',
      major: true,
      reason: 'Thiếu chữ ký',
    })
    expect(toStep(ev('complete')).tone).toBe('done')
    expect(toStep(ev('cancel')).tone).toBe('stop')
  })
  it('describes side notes', () => {
    expect(toStep(ev('files_changed', { added: 2, removed: 1 })).note).toBe(
      '+2 tệp, −1 tệp',
    )
    expect(toStep(ev('updated', { fields: ['title', 'checklist'] })).note).toBe(
      'Sửa tiêu đề, checklist',
    )
    expect(toStep(ev('due_changed', { from: null, to: null })).note).toBe(
      'Hạn: không hạn → không hạn',
    )
    expect(toStep(ev('files_changed')).major).toBe(false)
  })
  it('falls back for unknown actions', () => {
    expect(toStep(ev('mystery'))).toMatchObject({
      label: 'mystery',
      tone: 'note',
      major: false,
    })
  })
  it('folds older steps away only when it saves more than one', () => {
    const events = Array.from({ length: 7 }, (_, i) =>
      ev('updated', {}, String(i)),
    )
    expect(activitySteps(events, 6).hidden).toBe(0)
    const more = [...events, ev('start', {}, 'x')]
    const folded = activitySteps(more, 6)
    expect(folded.hidden).toBe(2)
    expect(folded.steps.at(-1)?.id).toBe('x')
  })
  it('lays the history out down the card, in order, every step joined to the next', () => {
    const steps = ['created', 'updated', 'start', 'complete'].map((a) => toStep(ev(a)))
    const { placed, links } = canvasLayout(steps, 'down')
    expect(placed.map((p) => p.x)).toEqual([0, 0, 0, 0])
    const ys = placed.map((p) => p.y)
    expect([...ys].sort((a, b) => a - b)).toEqual(ys)
    for (let i = 1; i < placed.length; i++) {
      expect(placed[i].y).toBeGreaterThanOrEqual(placed[i - 1].y + placed[i - 1].height)
    }
    expect(links.map((l) => [l.source, l.target, l.aside])).toEqual([
      ['created', 'updated', true],
      ['updated', 'start', true],
      ['start', 'complete', false],
    ])
    expect(placed.filter((p) => p.latest).map((p) => p.step.id)).toEqual(['complete'])
  })
  it('in the wide view keeps main steps on one line and hangs side notes under them', () => {
    const steps = ['created', 'updated', 'due_changed', 'start', 'complete'].map((a) => toStep(ev(a)))
    const { placed, links } = canvasLayout(steps, 'right')
    const at = Object.fromEntries(placed.map((p) => [p.step.id, p]))
    expect([at.created.y, at.start.y, at.complete.y]).toEqual([0, 0, 0])
    expect(at.created.x).toBeLessThan(at.start.x)
    expect(at.start.x).toBeLessThan(at.complete.x)
    // Both notes sit under "created", one below the other, below the main line.
    expect(at.updated.x).toBe(at.created.x)
    expect(at.due_changed.x).toBe(at.created.x)
    expect(at.updated.y).toBeGreaterThan(at.created.height)
    expect(at.due_changed.y).toBeGreaterThan(at.updated.y + at.updated.height)
    expect(links.map((l) => [l.source, l.target, l.aside])).toEqual([
      ['created', 'updated', true],
      ['updated', 'due_changed', true],
      ['created', 'start', false],
      ['start', 'complete', false],
    ])
  })
  it('wraps a long main line into rows below everything hanging off the row above', () => {
    const steps = ['created', 'files_changed', 'assigned', 'accept', 'start', 'submit'].map((a) => toStep(ev(a)))
    const { placed, links } = canvasLayout(steps, 'right', undefined, 2)
    const at = Object.fromEntries(placed.map((p) => [p.step.id, p]))
    expect([at.created.y, at.assigned.y]).toEqual([0, 0])
    const note = at.files_changed
    expect(at.accept.x).toBe(0)
    expect(at.accept.y).toBeGreaterThan(note.y + note.height)
    expect(at.submit.y).toBeGreaterThan(at.accept.y)
    const wrap = links.find((l) => l.target === 'accept')!
    expect(wrap.source).toBe('assigned')
    // The link back to the start of the next row runs between the rows, clear of the side note.
    expect(wrap.corridor).toBeGreaterThan(note.y + note.height)
    expect(wrap.corridor).toBeLessThan(at.accept.y)
    expect(links.find((l) => l.target === 'assigned')!.corridor).toBeUndefined()
    expect(stepsPerRow(1150)).toBe(4)
    expect(stepsPerRow(200)).toBe(1)
  })
})
