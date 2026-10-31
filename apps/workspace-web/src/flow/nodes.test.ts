// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
import { describe, expect, it } from 'vitest'
import { KINDS, TEMPLATES, summary, toApi, toCanvas, waitLabel } from './nodes'
import type { FlowNodeData } from './nodes'

describe('flow graph conversion', () => {
  it('keeps every template unchanged through the canvas and back', () => {
    for (const template of TEMPLATES) {
      const canvas = toCanvas(template.graph)
      expect(toApi(canvas.nodes, canvas.edges)).toEqual(template.graph)
    }
  })

  it('turns condition ports into branches and plain ports into none', () => {
    const template = TEMPLATES.find((t) => t.key === 'returned-reminder')!
    const { nodes, edges } = toCanvas(template.graph)
    const branches = toApi(nodes, edges).edges.map((e) => e.branch)
    expect(branches).toEqual([null, null, 'true'])
    expect(nodes.find((n) => n.id === 'trigger')?.deletable).toBe(false)
  })

  it('templates only use node kinds the editor knows, with one trigger each', () => {
    for (const template of TEMPLATES) {
      expect(template.graph.nodes.filter((n) => n.type === 'trigger')).toHaveLength(1)
      for (const node of template.graph.nodes) expect(KINDS[node.type]).toBeDefined()
    }
  })
})

describe('node summaries', () => {
  const triggers = [{ key: 'task.submitted', label: 'Công việc được nộp', fields: {}, sample: {} }]
  const name = (id: string) => (id === 'u1' ? 'An' : id)
  const data = (kind: FlowNodeData['kind'], config: Record<string, unknown>): FlowNodeData => ({
    kind,
    label: '',
    config,
  })

  it('describes what each node is set to do', () => {
    expect(summary(data('trigger', { event: 'task.submitted' }), triggers, name)).toBe('Công việc được nộp')
    expect(
      summary(
        data('if', {
          mode: 'any',
          conditions: [
            { field: 'priority', operator: 'eq', value: 'urgent' },
            { field: 'labels', operator: 'contains', value: 'gấp' },
          ],
        }),
        triggers,
        name,
      ),
    ).toBe('priority bằng "urgent" hoặc +1')
    expect(summary(data('notify', { recipients: ['creator', 'u1'] }), triggers, name)).toBe(
      'Tới Người giao việc, An',
    )
    expect(summary(data('wait', { minutes: 2880 }), triggers, name)).toBe('Chờ 2 ngày')
  })

  it('formats wait durations in the largest whole unit', () => {
    expect(waitLabel(45)).toBe('45 phút')
    expect(waitLabel(120)).toBe('2 giờ')
    expect(waitLabel(1440)).toBe('1 ngày')
  })
})
