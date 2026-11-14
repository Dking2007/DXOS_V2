// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
import { reactive } from 'vue'
import { describe, expect, it } from 'vitest'
import { KINDS, PROCESS_TEMPLATES, TEMPLATES, branchLabel, outputs, paintRun, paletteKinds, summary, toApi, toCanvas, tone, waitLabel, plainCopy, nodeOutputs } from './nodes'
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

describe('AI step', () => {
  it('says which answers it can give and where the answer goes', () => {
    const data = { kind: 'ai', label: '', config: KINDS.ai.defaults() } as FlowNodeData
    expect(summary(data, [], (id) => id)).toBe('Gấp / Bình thường → ai_label')
  })
})

describe('process flows', () => {
  it('every process template survives the canvas and only uses branches its nodes offer', () => {
    for (const template of PROCESS_TEMPLATES) {
      const canvas = toCanvas(template.graph)
      expect(toApi(canvas.nodes, canvas.edges)).toEqual(template.graph)
      const kinds = new Map(template.graph.nodes.map((node) => [node.id, node]))
      expect(template.graph.nodes.filter((n) => n.type === 'trigger')).toHaveLength(1)
      for (const edge of template.graph.edges) {
        const source = kinds.get(edge.source)!
        expect(KINDS[source.type].terminal).toBeUndefined()
        const exits = outputs(source.type, source.data)
        if (exits.length) expect(exits).toContain(edge.branch)
        else expect(edge.branch).toBeNull()
      }
    }
  })

  it('offers approval exits by configuration and keeps process steps out of automations', () => {
    expect(outputs('approval', {})).toEqual(['approve', 'return', 'reject'])
    expect(outputs('approval', { allow_return: false })).toEqual(['approve', 'reject'])
    expect(outputs('assign_task', {})).toEqual(['completed', 'cancelled'])
    expect(paletteKinds()).toEqual(expect.arrayContaining(['approval', 'consult', 'finish', 'notify']))
    expect([tone('approve'), tone('return'), tone('reject')]).toEqual(['good', 'warn', 'bad'])
    expect(branchLabel('consult', 'approve')).toBe('Đồng ý')
  })

  it('paints a run: states on nodes, the outcome on the node that settled it, lit edges', () => {
    const template = PROCESS_TEMPLATES.find((t) => t.key === 'process-documents')!
    const canvas = toCanvas(template.graph)
    const painted = paintRun(canvas.nodes, canvas.edges, [
      { node_id: 'trigger', type: 'trigger', state: 'succeeded' },
      { node_id: 'has_files', type: 'if', state: 'succeeded', branch: 'false' },
      { node_id: 'more', type: 'request_info', state: 'succeeded', outcome: 'needs_revision' },
      { node_id: null, type: 'outcome', state: 'succeeded', outcome: 'needs_revision', source: 'more' },
    ])
    const byId = Object.fromEntries(painted.nodes.map((node) => [node.id, node.data]))
    expect(byId.more.outcome).toBe('needs_revision')
    expect(byId.leader.status).toBeUndefined()
    const lit = painted.edges.filter((edge) => edge.animated).map((edge) => edge.target)
    expect(lit.sort()).toEqual(['has_files', 'more'])
  })

  it('describes a process trigger by its form and an approval by who decides', () => {
    const trigger: FlowNodeData = { kind: 'trigger', label: '', config: { event: 'case.submitted', form_id: 'f1' } }
    expect(summary(trigger, [], () => '', [{ id: 'f1', name: 'Đề nghị mua sắm' }])).toBe('Khi trình “Đề nghị mua sắm”')
    const approval: FlowNodeData = { kind: 'approval', label: '', config: { resolver: 'user', user_id: 'u1' } }
    expect(summary(approval, [], () => 'Giám đốc')).toBe('Giám đốc')
  })
})

describe('copying a graph', () => {
  it('accepts the reactive data queries hand out', () => {
    const data = reactive({ graph: { nodes: [{ id: 'a', data: { user_ids: ['x'] } }] } })
    const copy = plainCopy(data.graph)
    copy.nodes[0]!.data.user_ids.push('y')
    expect(data.graph.nodes[0]!.data.user_ids).toEqual(['x'])
  })
  it('draws a stored process without failing on reactive nodes', () => {
    const graph = reactive(plainCopy(PROCESS_TEMPLATES[0]!.graph))
    expect(toCanvas(graph).nodes.length).toBe(graph.nodes.length)
  })
})

describe('steps added to processes', () => {
  it('offers the overdue exit only where the step takes it', () => {
    expect(outputs('approval', {})).not.toContain('overdue')
    expect(outputs('approval', { overdue: { action: 'remind' } })).not.toContain('overdue')
    expect(outputs('approval', { overdue: { action: 'branch' } })).toContain('overdue')
    expect(outputs('input', {})).toEqual(['submitted'])
    expect(outputs('subprocess', {})).toEqual(['approve', 'return', 'reject'])
  })
  it('never offers the node a sub-process ending is drawn with', () => {
    expect(paletteKinds()).toContain('input')
    expect(paletteKinds()).toContain('subprocess')
    expect(paletteKinds()).not.toContain('sub_end')
  })
  it('paints only the latest pass of a step sent back to', () => {
    const graph = toCanvas({
      nodes: [{ id: 'a', type: 'approval', label: '', position: { x: 0, y: 0 }, data: {} }],
      edges: [],
    })
    const painted = paintRun(graph.nodes, graph.edges, [
      { node_id: 'a', type: 'approval', state: 'succeeded', branch: 'approve', superseded: true },
      { node_id: 'a', type: 'approval', state: 'waiting', attempt: 2 },
    ])
    expect(painted.nodes[0]!.data!.status).toBe('waiting')
    expect(painted.nodes[0]!.data!.message).toBe('Lần 2')
  })
})

describe('results steps produce', () => {
  it('names them after the step, or the name it was given', () => {
    expect(nodeOutputs('Duyet-1', 'approval', {}, 'Duyệt')['duyet_1.decision']).toBe('Duyệt: Quyết định')
    expect(Object.keys(nodeOutputs('a', 'create_document', { output_name: 'van_ban' }))).toContain('van_ban.file_id')
  })
  it('includes what the step asks people to hand in', () => {
    const fields = [{ key: 'ket_luan', label: 'Kết luận' }]
    expect(nodeOutputs('a', 'approval', { result_fields: fields }, 'Bước')['a.ket_luan']).toBe('Bước: Kết luận')
  })
  it('reads a value set by name directly', () => {
    expect(nodeOutputs('a', 'set_value', { name: 'tong' })).toEqual({ tong: 'Giá trị đã đặt' })
  })
})

describe('a switch', () => {
  it('has one exit per case and one for the rest, labelled by its cases', () => {
    const config = { cases: [{ label: 'Lớn' }, { label: 'Nhỏ' }] }
    expect(outputs('switch', config)).toEqual(['case_1', 'case_2', 'default'])
    expect(branchLabel('switch', 'case_2', config)).toBe('Nhỏ')
    expect(branchLabel('switch', 'default', config)).toBe('Còn lại')
  })
})
