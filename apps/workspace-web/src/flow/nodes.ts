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
    key: 'returned-reminder',
    title: 'Việc trả lại chưa làm lại sau 1 ngày → nhắc',
    description:
      'Người làm đã được báo khi việc bị trả lại. Luồng chờ 1 ngày, nếu việc vẫn ở trạng thái Trả lại thì nhắc cả người làm và người giao.',
    graph: {
      nodes: [
        n('trigger', 'trigger', 0, 60, { event: 'task.returned' }),
        n('wait_day', 'wait', 300, 60, { minutes: 1440 }),
        n('if_still', 'if', 600, 60, {
          mode: 'all',
          conditions: [{ field: 'status', operator: 'eq', value: 'returned' }],
        }),
        n('notify_both', 'notify', 920, 60, {
          recipients: ['assignee', 'creator'],
          title: 'Việc bị trả lại vẫn chưa được làm lại: {title}',
        }),
      ],
      edges: [e('trigger', 'wait_day'), e('wait_day', 'if_still'), e('if_still', 'notify_both', 'true')],
    },
  },
  {
    key: 'case-revision-reminder',
    title: 'Hồ sơ trả lại chưa trình lại sau 2 ngày → nhắc',
    description:
      'Nếu sau 2 ngày hồ sơ vẫn ở trạng thái Cần chỉnh sửa thì nhắc người lập và lãnh đạo đơn vị.',
    graph: {
      nodes: [
        n('trigger', 'trigger', 0, 60, { event: 'case.needs_revision' }),
        n('wait_days', 'wait', 300, 60, { minutes: 2880 }),
        n('if_still', 'if', 600, 60, {
          mode: 'all',
          conditions: [{ field: 'status', operator: 'eq', value: 'needs_revision' }],
        }),
        n('notify_owner', 'notify', 920, 60, {
          recipients: ['owner', 'department_manager'],
          title: 'Hồ sơ bị trả lại chưa được trình lại: {title}',
        }),
      ],
      edges: [e('trigger', 'wait_days'), e('wait_days', 'if_still'), e('if_still', 'notify_owner', 'true')],
    },
  },
  {
    key: 'urgent-submitted',
    title: 'Việc khẩn được nộp → báo lãnh đạo đơn vị',
    description: 'Người giao đã được báo sẵn khi có kết quả. Luồng báo thêm lãnh đạo đơn vị nếu việc có ưu tiên Khẩn.',
    graph: {
      nodes: [
        n('trigger', 'trigger', 0, 80, { event: 'task.submitted' }),
        n('if_urgent', 'if', 300, 80, {
          mode: 'all',
          conditions: [{ field: 'priority', operator: 'eq', value: 'urgent' }],
        }),
        n('notify_leader', 'notify', 620, 80, {
          recipients: ['department_manager'],
          title: 'Việc khẩn đã nộp kết quả: {title}',
        }),
      ],
      edges: [e('trigger', 'if_urgent'), e('if_urgent', 'notify_leader', 'true')],
    },
  },
  {
    key: 'case-approved',
    title: 'Hồ sơ được duyệt → tạo việc lưu trữ',
    description:
      'Tạo một việc lưu trữ gắn với hồ sơ, hạn 3 ngày. Chọn người hoặc phòng nhận việc trong node. Người lập hồ sơ đã được báo kết quả sẵn.',
    graph: {
      nodes: [
        n('trigger', 'trigger', 0, 60, { event: 'case.approved' }),
        n('task_archive', 'create_task', 320, 60, {
          title: 'Lưu trữ hồ sơ: {title}',
          priority: 'normal',
          due_in_days: 3,
        }),
      ],
      edges: [e('trigger', 'task_archive')],
    },
  },
]
