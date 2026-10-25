// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
import type { Component } from 'vue'
import type { Edge, Node } from '@vue-flow/core'
import { Bell, GitBranch, Hourglass, ListPlus, Webhook, Zap } from 'lucide-vue-next'

export type NodeKind = 'trigger' | 'if' | 'notify' | 'create_task' | 'webhook' | 'wait'

export interface FlowCondition {
  field: string
  operator: string
  value: unknown
}
export interface FlowNodeData {
  kind: NodeKind
  label: string
  config: Record<string, unknown>
  /** Overlay from a test or a recorded run; never saved. */
  status?: 'succeeded' | 'failed' | 'waiting' | 'queued' | 'would_run' | 'unknown' | 'skipped'
  branch?: 'true' | 'false'
  errors?: string[]
  message?: string
}
/** The graph shape the Workspace API stores. */
export interface ApiGraph {
  nodes: {
    id: string
    type: NodeKind
    label: string
    position: { x: number; y: number }
    data: Record<string, unknown>
  }[]
  edges: { id: string; source: string; target: string; branch: 'true' | 'false' | null }[]
}
export interface TriggerInfo {
  key: string
  label: string
  fields: Record<string, string>
  sample: Record<string, unknown>
  /** Whether people may attach a flow with this trigger to individual tasks. */
  attachable?: boolean
}

interface KindMeta {
  title: string
  group: 'Kích hoạt' | 'Logic' | 'Hành động'
  hint: string
  icon: Component
  color: string
  defaults: () => Record<string, unknown>
}
export const KINDS: Record<NodeKind, KindMeta> = {
  trigger: {
    title: 'Khi sự kiện xảy ra',
    group: 'Kích hoạt',
    hint: 'Điểm bắt đầu của luồng',
    icon: Zap,
    color: '#e8833a',
    defaults: () => ({ event: 'task.submitted' }),
  },
  if: {
    title: 'Điều kiện',
    group: 'Logic',
    hint: 'Rẽ nhánh Đúng / Sai',
    icon: GitBranch,
    color: '#7a5cd6',
    defaults: () => ({ mode: 'all', conditions: [{ field: 'priority', operator: 'eq', value: 'urgent' }] }),
  },
  wait: {
    title: 'Chờ',
    group: 'Logic',
    hint: 'Tạm dừng rồi chạy tiếp',
    icon: Hourglass,
    color: '#5b6b7d',
    defaults: () => ({ minutes: 60 }),
  },
  notify: {
    title: 'Gửi thông báo',
    group: 'Hành động',
    hint: 'Thông báo trong ứng dụng',
    icon: Bell,
    color: '#0f8e9a',
    defaults: () => ({ recipients: ['assignee'], title: 'Cập nhật: {title}' }),
  },
  create_task: {
    title: 'Tạo công việc',
    group: 'Hành động',
    hint: 'Giao việc tự động',
    icon: ListPlus,
    color: '#2f7fd1',
    defaults: () => ({ title: 'Theo dõi: {title}', priority: 'normal', due_in_days: 2 }),
  },
  webhook: {
    title: 'Gọi webhook',
    group: 'Hành động',
    hint: 'Gửi dữ liệu sang hệ thống khác',
    icon: Webhook,
    color: '#c24f7a',
    defaults: () => ({ connection_id: null, path: '' }),
  },
}

export const OPERATORS: Record<string, string> = {
  eq: 'bằng',
  ne: 'khác',
  contains: 'chứa',
  in: 'thuộc danh sách',
  gt: 'lớn hơn',
  gte: 'từ',
  lt: 'nhỏ hơn',
  lte: 'đến',
  empty: 'trống',
  not_empty: 'có giá trị',
}
export const RECIPIENTS: Record<string, string> = {
  assignee: 'Người phụ trách',
  creator: 'Người giao việc',
  owner: 'Người tạo hồ sơ',
  author: 'Người đăng bài',
  department_manager: 'Lãnh đạo đơn vị',
}
const PRIORITY: Record<string, string> = { low: 'Thấp', normal: 'Bình thường', high: 'Cao', urgent: 'Khẩn' }

export function waitLabel(minutes: number) {
  if (minutes % 1440 === 0) return `${minutes / 1440} ngày`
  if (minutes % 60 === 0) return `${minutes / 60} giờ`
  return `${minutes} phút`
}

/** One line under the node title saying what it is set to do. */
export function summary(
  data: FlowNodeData,
  triggers: TriggerInfo[],
  names: (id: string) => string,
): string {
  const c = data.config
  switch (data.kind) {
    case 'trigger':
      return triggers.find((t) => t.key === c.event)?.label ?? 'Chọn sự kiện'
    case 'if': {
      const list = (c.conditions as FlowCondition[]) ?? []
      if (!list.length) return 'Chưa có điều kiện'
      const first = list[0]
      const text = `${first.field} ${OPERATORS[first.operator] ?? first.operator}${
        ['empty', 'not_empty'].includes(first.operator) ? '' : ` ${JSON.stringify(first.value)}`
      }`
      return list.length > 1 ? `${text} ${c.mode === 'any' ? 'hoặc' : 'và'} +${list.length - 1}` : text
    }
    case 'wait':
      return `Chờ ${waitLabel(Number(c.minutes ?? 60))}`
    case 'notify': {
      const people = ((c.recipients as string[]) ?? []).map((r) => RECIPIENTS[r] ?? names(r))
      return people.length ? `Tới ${people.join(', ')}` : 'Chọn người nhận'
    }
    case 'create_task':
      return c.assignee_id
        ? `Giao ${names(String(c.assignee_id))} · ${PRIORITY[String(c.priority)] ?? ''}`
        : c.department_id
          ? 'Giao cho đơn vị'
          : 'Chọn người nhận việc'
    case 'webhook':
      return c.connection_id ? `POST /${String(c.path ?? '')}` : 'Chọn kết nối'
  }
}

export function toCanvas(graph: ApiGraph): { nodes: Node<FlowNodeData>[]; edges: Edge[] } {
  return {
    nodes: graph.nodes.map((node) => ({
      id: node.id,
      type: 'flow',
      position: { ...node.position },
      data: { kind: node.type, label: node.label, config: structuredClone(node.data) },
      deletable: node.type !== 'trigger',
    })),
    edges: graph.edges.map((edge) => canvasEdge(edge.source, edge.target, edge.branch ?? undefined)),
  }
}

export function canvasEdge(source: string, target: string, handle?: string | null): Edge {
  return {
    id: `${source}${handle ? `:${handle}` : ''}->${target}`,
    source,
    target,
    sourceHandle: handle || undefined,
    type: 'smoothstep',
    // Branch edges are coloured; the Đúng/Sai tags sit on the condition node's ports.
    class: handle ? `edge-${handle}` : undefined,
  }
}

export function toApi(nodes: Node<FlowNodeData>[], edges: Edge[]): ApiGraph {
  return {
    nodes: nodes.map((node) => ({
      id: node.id,
      type: node.data!.kind,
      label: node.data!.label ?? '',
      position: { x: Math.round(node.position.x), y: Math.round(node.position.y) },
      data: node.data!.config,
    })),
    edges: edges.map((edge) => ({
      id: edge.id.slice(0, 90),
      source: edge.source,
      target: edge.target,
      branch: (edge.sourceHandle as 'true' | 'false' | undefined) ?? null,
    })),
  }
}

function n(id: string, type: NodeKind, x: number, y: number, data?: Record<string, unknown>) {
  return { id, type, label: '', position: { x, y }, data: data ?? KINDS[type].defaults() }
}
function e(source: string, target: string, branch: 'true' | 'false' | null = null) {
  return { id: `${source}${branch ? `:${branch}` : ''}->${target}`, source, target, branch }
}

export const TEMPLATES: { key: string; title: string; description: string; graph: ApiGraph }[] = [
  {
    key: 'blank',
    title: 'Luồng trống',
    description: 'Bắt đầu từ node kích hoạt và tự thêm các bước.',
    graph: { nodes: [n('trigger', 'trigger', 0, 0)], edges: [] },
  },
  {
    key: 'urgent-submitted',
    title: 'Việc khẩn được nộp → báo lãnh đạo',
    description: 'Nếu việc có ưu tiên Khẩn thì báo lãnh đạo đơn vị và người giao; nếu không thì chỉ báo người giao.',
    graph: {
      nodes: [
        n('trigger', 'trigger', 0, 80, { event: 'task.submitted' }),
        n('if_urgent', 'if', 300, 80, {
          mode: 'all',
          conditions: [{ field: 'priority', operator: 'eq', value: 'urgent' }],
        }),
        n('notify_leader', 'notify', 620, 0, {
          recipients: ['department_manager', 'creator'],
          title: 'Việc khẩn đã nộp kết quả: {title}',
        }),
        n('notify_creator', 'notify', 620, 180, {
          recipients: ['creator'],
          title: 'Có kết quả cần nghiệm thu: {title}',
        }),
      ],
      edges: [
        e('trigger', 'if_urgent'),
        e('if_urgent', 'notify_leader', 'true'),
        e('if_urgent', 'notify_creator', 'false'),
      ],
    },
  },
  {
    key: 'case-approved',
    title: 'Hồ sơ được duyệt → tạo việc lưu trữ',
    description: 'Mỗi hồ sơ được phê duyệt tự sinh một việc lưu trữ cho người phụ trách.',
    graph: {
      nodes: [
        n('trigger', 'trigger', 0, 60, { event: 'case.approved' }),
        n('task_archive', 'create_task', 320, 0, {
          title: 'Lưu trữ hồ sơ: {title}',
          priority: 'normal',
          due_in_days: 3,
        }),
        n('notify_owner', 'notify', 320, 160, {
          recipients: ['owner'],
          title: 'Hồ sơ đã được duyệt: {title}',
        }),
      ],
      edges: [e('trigger', 'task_archive'), e('trigger', 'notify_owner')],
    },
  },
  {
    key: 'returned-reminder',
    title: 'Việc bị trả lại → nhắc sau 1 ngày',
    description: 'Báo ngay cho người phụ trách, chờ 1 ngày rồi nhắc lại người giao theo dõi.',
    graph: {
      nodes: [
        n('trigger', 'trigger', 0, 60, { event: 'task.returned' }),
        n('notify_now', 'notify', 300, 60, { recipients: ['assignee'], title: 'Việc bị trả lại: {title}' }),
        n('wait_day', 'wait', 600, 60, { minutes: 1440 }),
        n('notify_later', 'notify', 900, 60, {
          recipients: ['creator'],
          title: 'Theo dõi việc đã trả lại hôm qua: {title}',
        }),
      ],
      edges: [e('trigger', 'notify_now'), e('notify_now', 'wait_day'), e('wait_day', 'notify_later')],
    },
  },
]
