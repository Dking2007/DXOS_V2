// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
import { describe, expect, it } from 'vitest'
import { READABLE_ZOOM, narrowViewport } from './layout'
import type { Area, Viewport } from './layout'

const step = (column: number, row = 0): Area => ({ x: column * 360, y: row * 128, width: 250, height: 80 })
const onScreen = (box: Area, view: Viewport) => ({
  left: view.x + box.x * view.zoom,
  right: view.x + (box.x + box.width) * view.zoom,
  top: view.y + box.y * view.zoom,
  bottom: view.y + (box.y + box.height) * view.zoom,
})
const phone = { width: 360, height: 510 }

describe('opening view on a narrow canvas', () => {
  it('shows a flow that fits at a readable size whole and centred, never past 100%', () => {
    const boxes = [step(0)]
    const view = narrowViewport(boxes, phone)
    expect(view.zoom).toBe(1)
    const box = onScreen(boxes[0]!, view)
    expect(box.left).toBeCloseTo(phone.width - box.right)
    expect(box.top).toBeCloseTo(phone.height - box.bottom)
  })

  it('keeps a long flow readable and starts it at the trigger instead of shrinking it to a thumbnail', () => {
    // Five steps in a row: fitting them all on 360px would need about 20%.
    const boxes = [0, 1, 2, 3, 4].map((column) => step(column))
    const view = narrowViewport(boxes, phone, { start: boxes[0] })
    expect(view.zoom).toBe(READABLE_ZOOM)
    const first = onScreen(boxes[0]!, view)
    expect(first.left).toBe(16)
    expect(first.right).toBeLessThanOrEqual(phone.width)
    // The row sits in the middle of the pane, not at the top.
    expect((first.top + first.bottom) / 2).toBeCloseTo(phone.height / 2)
  })

  it('uses the largest zoom that shows everything when that is still readable', () => {
    const boxes = [step(0), step(1)]
    const view = narrowViewport(boxes, { width: 520, height: 600 })
    expect(view.zoom).toBeGreaterThanOrEqual(READABLE_ZOOM)
    expect(view.zoom).toBeLessThan(1)
    expect(onScreen(boxes[0]!, view).left).toBeGreaterThanOrEqual(16 - 1e-9)
    expect(onScreen(boxes[1]!, view).right).toBeLessThanOrEqual(520 - 16 + 1e-9)
  })

  it('in a flow taller than the pane, centres the trigger row without leaving space above the flow', () => {
    // Trigger on the first row of a tall branching flow.
    const boxes = [step(0, 0), ...[0, 1, 2, 3, 4, 5, 6, 7].map((row) => step(1, row))]
    const view = narrowViewport(boxes, phone, { start: boxes[0] })
    expect(view.zoom).toBe(READABLE_ZOOM)
    expect(onScreen(boxes[0]!, view).top).toBeCloseTo(16)
    // Trigger in the middle of the flow: its row is in the middle of the pane.
    const middle = [step(0, 4), ...[0, 1, 2, 3, 4, 5, 6, 7, 8].map((row) => step(1, row))]
    const centred = onScreen(middle[0]!, narrowViewport(middle, phone, { start: middle[0] }))
    expect((centred.top + centred.bottom) / 2).toBeCloseTo(phone.height / 2)
  })

  it('leaves an empty canvas at 100%', () => {
    expect(narrowViewport([], phone)).toEqual({ x: 0, y: 0, zoom: 1 })
  })
})
