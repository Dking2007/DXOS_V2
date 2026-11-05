// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
import type { Component } from 'vue'
import type { Edge, Node } from '@vue-flow/core'
import {
  Bell,
  ClipboardCheck,
  FilePen,
  Flag,
  GitBranch,
  Hourglass,
  ListPlus,
  Sparkles,
  UserCheck,
  Users,
  Webhook,
  Zap,
} from 'lucide-vue-next'

export type NodeKind =
  | 'trigger'
  | 'if'
  | 'notify'
  | 'create_task'
  | 'webhook'
  | 'wait'
  | 'ai'
  | 'approval'
  | 'consult'
  | 'assign_task'
  | 'request_info'
  | 'finish'
/** "automation" reacts to events; "process" is the route a form's dossiers follow. */
export type FlowKind = 'automation' | 'process'
export type Branch = 'true' | 'false' | 'approve' | 'return' | 'reject' | 'completed' | 'cancelled'

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
  status?: 'succeeded' | 'failed' | 'waiting' | 'queued' | 'would_run' | 'unknown' | 'skipped' | 'cancelled'
  branch?: Branch
  errors?: string[]
  message?: string
  /** Process runs: how the dossier ended when this node settled it. */
  outcome?: string
  /** Who was asked at this step, from a run. */
  people?: string[]
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
  edges: { id: string; source: string; target: string; branch: Branch | null }[]
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
  group: 'Kích hoạt' | 'Logic' | 'Hành động' | 'Bước quy trình'
  hint: string
  icon: Component
  color: string
  defaults: () => Record<string, unknown>
  /** Only offered when drawing a dossier's process. */
  process?: true
  /** Settles the dossier; nothing follows it. */
  terminal?: true
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
  ai: {
    title: 'Hỏi AI',
    group: 'Logic',
    hint: 'AI phân loại để rẽ nhánh',
    icon: Sparkles,
    color: '#6d4fd0',
    defaults: () => ({ question: 'Việc này có gấp không?', choices: ['Gấp', 'Bình thường'], output: 'ai_label' }),
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
  approval: {
    title: 'Duyệt',
    group: 'Bước quy trình',
    hint: 'Một người duyệt, trả lại hoặc từ chối',
    icon: UserCheck,
    color: '#1f8a5b',
    process: true,
    defaults: () => ({
      resolver: 'department_manager',
      user_id: null,
      allow_return: true,
      allow_reject: true,
      due_in_days: 3,
      instructions: '',
    }),
  },
  consult: {
    title: 'Xin ý kiến',
    group: 'Bước quy trình',
    hint: 'Nhiều người cho ý kiến cùng lúc',
    icon: Users,
    color: '#3d7bb8',
    process: true,
    defaults: () => ({
      user_ids: [],
      include_department_manager: false,
      mode: 'all',
      due_in_days: 2,
      instructions: '',
    }),
  },
  assign_task: {
    title: 'Giao việc và chờ',
    group: 'Bước quy trình',
    hint: 'Giao việc, đi tiếp khi việc được nghiệm thu',
    icon: ClipboardCheck,
    color: '#2f6fb0',
    process: true,
    defaults: () => ({ title: 'Thẩm định hồ sơ: {title}', priority: 'normal', due_in_days: 3 }),
  },
  request_info: {
    title: 'Yêu cầu bổ sung',
    group: 'Bước quy trình',
    hint: 'Trả hồ sơ để người tạo bổ sung',
    icon: FilePen,
    color: '#c27a1a',
    process: true,
    terminal: true,
    defaults: () => ({ message: 'Đề nghị bổ sung tài liệu cho hồ sơ.' }),
  },
  finish: {
    title: 'Kết thúc',
    group: 'Bước quy trình',
    hint: 'Chốt kết quả: duyệt hoặc từ chối',
    icon: Flag,
    color: '#44536a',
    process: true,
    terminal: true,
    defaults: () => ({ result: 'approved', message: '' }),
  },
}

export const BRANCH_LABELS: Record<Branch, string> = {
  true: 'Đúng',
  false: 'Sai',
  approve: 'Duyệt',
  return: 'Trả lại',
  reject: 'Từ chối',
  completed: 'Xong',
  cancelled: 'Hủy',
}
/** Colour family of a branch: carrying on, stopping, or going back for changes. */
export function tone(branch: string | null | undefined): 'good' | 'bad' | 'warn' | undefined {
  if (!branch) return undefined
  if (branch === 'return') return 'warn'
  return ['true', 'approve', 'completed'].includes(branch) ? 'good' : 'bad'
}
/** Named exits of a node, in display order; an empty list means a single plain exit. */
export function outputs(kind: NodeKind, config: Record<string, unknown>): Branch[] {
  switch (kind) {
    case 'if':
      return ['true', 'false']
    case 'approval':
      return [
        'approve',
        ...(config.allow_return === false ? [] : (['return'] as Branch[])),
        ...(config.allow_reject === false ? [] : (['reject'] as Branch[])),
      ]
    case 'consult':
      return ['approve', 'reject']
    case 'assign_task':
      return ['completed', 'cancelled']
    default:
      return []
  }
}
/** Label of a branch on a given node: opinions agree or disagree rather than approve. */
export function branchLabel(kind: NodeKind, branch: Branch) {
  if (kind === 'consult') return branch === 'approve' ? 'Đồng ý' : 'Không đồng ý'
  return BRANCH_LABELS[branch]
}
export const OUTCOMES: Record<string, string> = {
  approved: 'Đã duyệt',
  rejected: 'Từ chối',
  needs_revision: 'Yêu cầu bổ sung',
}
/** Kinds offered in the palette of a flow of this kind. */
export function paletteKinds(flow: FlowKind): NodeKind[] {
  return (Object.keys(KINDS) as NodeKind[]).filter(
    (kind) => kind !== 'trigger' && (flow === 'process' || !KINDS[kind].process),
  )
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
const RESOLVERS: Record<string, string> = { department_manager: 'Lãnh đạo đơn vị của hồ sơ', user: 'Người cụ thể' }
export { RESOLVERS }
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
  forms: { id: string; name: string }[] = [],
): string {
  const c = data.config
  switch (data.kind) {
    case 'trigger':
      if ('form_id' in c) {
        const form = forms.find((f) => f.id === c.form_id)
        return form ? `Khi trình “${form.name}”` : 'Chọn biểu mẫu'
      }
      return triggers.find((t) => t.key === c.event)?.label ?? 'Chọn sự kiện'
    case 'approval': {
      if (data.people?.length) return data.people.join(', ')
      const who = c.resolver === 'user' ? (c.user_id ? names(String(c.user_id)) : 'Chọn người duyệt') : 'Lãnh đạo đơn vị'
      return c.due_in_days != null ? `${who} · ${c.due_in_days} ngày` : who
    }
    case 'consult': {
      if (data.people?.length) return data.people.join(', ')
      const people = ((c.user_ids as string[]) ?? []).map(names)
      if (c.include_department_manager) people.push('Lãnh đạo đơn vị')
      if (!people.length) return 'Chọn người cho ý kiến'
      return `${people.length} người · ${c.mode === 'any' ? 'một người đồng ý là đủ' : 'cần tất cả đồng ý'}`
    }
    case 'assign_task':
      return c.assignee_id ? `Giao ${names(String(c.assignee_id))}, chờ nghiệm thu` : c.department_id ? 'Giao cho đơn vị, chờ nghiệm thu' : 'Chọn người nhận việc'
    case 'request_info':
      return String(c.message || 'Trả hồ sơ để bổ sung')
    case 'finish':
      return c.result === 'rejected' ? 'Hồ sơ bị từ chối' : 'Hồ sơ được duyệt'
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
    case 'ai':
      return `${((c.choices as string[]) ?? []).join(' / ') || 'Thêm lựa chọn'} → ${String(c.output ?? 'ai_label')}`
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
    // Branch edges are coloured by meaning; the branch tags sit on the node's ports.
    class: handle ? `edge-${tone(handle)}` : undefined,
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
      branch: (edge.sourceHandle as Branch | undefined) ?? null,
    })),
  }
}

function n(id: string, type: NodeKind, x: number, y: number, data?: Record<string, unknown>) {
  return { id, type, label: '', position: { x, y }, data: data ?? KINDS[type].defaults() }
}
function e(source: string, target: string, branch: Branch | null = null) {
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

/** The trigger every process starts from; the form is chosen when the flow is drawn. */
function start(x = 0, y = 0) {
  return n('trigger', 'trigger', x, y, { event: 'case.submitted', form_id: null })
}
function step(id: string, type: NodeKind, x: number, y: number, label: string, data?: Record<string, unknown>) {
  return { ...n(id, type, x, y, { ...KINDS[type].defaults(), ...data }), label }
}

/** Ready-made processes people start from, then adjust to their form. */
export const PROCESS_TEMPLATES: { key: string; title: string; description: string; graph: ApiGraph }[] = [
  {
    key: 'process-one-level',
    title: 'Lãnh đạo đơn vị duyệt',
    description: 'Một bước duyệt. Duyệt thì hồ sơ được duyệt, trả lại thì người tạo bổ sung, từ chối thì kết thúc.',
    graph: {
      nodes: [start(), step('leader', 'approval', 320, 0, 'Lãnh đạo đơn vị duyệt')],
      edges: [e('trigger', 'leader')],
    },
  },
  {
    key: 'process-two-levels',
    title: 'Hai cấp: đơn vị rồi ban giám đốc',
    description: 'Lãnh đạo đơn vị duyệt trước; được duyệt thì chuyển một người ở ban giám đốc duyệt tiếp.',
    graph: {
      nodes: [
        start(),
        step('leader', 'approval', 320, 0, 'Lãnh đạo đơn vị duyệt'),
        step('board', 'approval', 680, -40, 'Ban giám đốc duyệt', { resolver: 'user' }),
      ],
      edges: [e('trigger', 'leader'), e('leader', 'board', 'approve')],
    },
  },
  {
    key: 'process-documents',
    title: 'Kiểm tra tài liệu rồi duyệt',
    description: 'Hồ sơ phải kèm ít nhất một tài liệu; thiếu thì tự trả về để bổ sung, đủ thì lãnh đạo đơn vị duyệt.',
    graph: {
      nodes: [
        start(),
        n('has_files', 'if', 320, 0, {
          mode: 'all',
          conditions: [{ field: 'file_count', operator: 'gt', value: 0 }],
        }),
        step('leader', 'approval', 680, -80, 'Lãnh đạo đơn vị duyệt'),
        step('more', 'request_info', 680, 120, 'Thiếu tài liệu', {
          message: 'Hồ sơ cần đính kèm tờ trình hoặc văn bản liên quan.',
        }),
      ],
      edges: [e('trigger', 'has_files'), e('has_files', 'leader', 'true'), e('has_files', 'more', 'false')],
    },
  },
  {
    key: 'process-consult',
    title: 'Xin ý kiến các bên rồi lãnh đạo quyết',
    description:
      'Gửi xin ý kiến nhiều người cùng lúc; dù đồng ý hay không, lãnh đạo đơn vị là người quyết định cuối và được thấy các ý kiến.',
    graph: {
      nodes: [
        start(),
        step('opinions', 'consult', 320, 0, 'Xin ý kiến các phòng'),
        step('leader', 'approval', 720, 0, 'Lãnh đạo quyết định'),
      ],
      edges: [e('trigger', 'opinions'), e('opinions', 'leader', 'approve'), e('opinions', 'leader', 'reject')],
    },
  },
  {
    key: 'process-appraisal',
    title: 'Giao thẩm định rồi duyệt',
    description:
      'Giao một việc thẩm định gắn với hồ sơ; khi việc được nghiệm thu thì chuyển lãnh đạo duyệt, việc bị hủy thì trả hồ sơ.',
    graph: {
      nodes: [
        start(),
        step('appraise', 'assign_task', 320, 0, 'Thẩm định hồ sơ'),
        step('leader', 'approval', 720, -80, 'Lãnh đạo đơn vị duyệt'),
        step('stop', 'request_info', 720, 120, 'Không thẩm định được', {
          message: 'Việc thẩm định bị hủy; đề nghị kiểm tra lại hồ sơ.',
        }),
        n('tell_owner', 'notify', 1080, -200, {
          recipients: ['owner'],
          title: 'Hồ sơ đã thẩm định xong, đang chờ duyệt: {title}',
        }),
      ],
      edges: [
        e('trigger', 'appraise'),
        e('appraise', 'leader', 'completed'),
        e('appraise', 'tell_owner', 'completed'),
        e('appraise', 'stop', 'cancelled'),
      ],
    },
  },
]

/** One recorded or simulated step, as the API returns it. */
export interface RunStep {
  node_id: string | null
  type: string
  state: string
  branch?: Branch
  message?: string
  title?: string
  people?: string[]
  outcome?: string
  /** On an outcome step: the node that settled the dossier. */
  source?: string
}
/** Paint a run on the canvas: each node gets its state, each taken edge lights up. */
export function paintRun(nodes: Node<FlowNodeData>[], edges: Edge[], steps: RunStep[]) {
  const byNode = new Map(steps.filter((s) => s.node_id).map((s) => [s.node_id!, s]))
  const settled = steps.find((s) => s.type === 'outcome')
  return {
    nodes: nodes.map((node) => {
      const step = byNode.get(node.id)
      return {
        ...node,
        data: {
          ...node.data!,
          status: step?.state as FlowNodeData['status'],
          branch: step?.branch,
          message: step?.message ?? (step?.title ? `“${step.title}”` : undefined),
          people: step?.people,
          outcome: settled?.source === node.id ? settled.outcome : undefined,
        },
      }
    }),
    edges: edges.map((edge) => {
      const from = byNode.get(edge.source)
      const active = !!from && byNode.has(edge.target) && (!edge.sourceHandle || from.branch === edge.sourceHandle)
      const kind = edge.sourceHandle ? `edge-${tone(edge.sourceHandle)}` : ''
      return { ...edge, animated: active, class: [kind, active ? 'edge-active' : ''].join(' ') }
    }),
  }
}
