// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
import type { Component } from 'vue'
import { roleLabel } from '../ui/labels'
import type { Edge, Node } from '@vue-flow/core'
import {
  Bell,
  BookCheck,
  Calculator,
  CalendarClock,
  Columns3,
  Download,
  FilePlus2,
  FileText,
  FolderInput,
  Mail,
  Merge,
  MessageSquare,
  PencilLine,
  ScanText,
  Split,
  ClipboardCheck,
  FilePen,
  Flag,
  GitBranch,
  Hourglass,
  ListPlus,
  Sparkles,
  TextCursorInput,
  UserCheck,
  Users,
  Webhook,
  Workflow,
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
  | 'input'
  | 'subprocess'
  | 'sub_end'
  | 'acknowledge'
  | 'switch'
  | 'parallel'
  | 'join'
  | 'wait_until'
  | 'set_value'
  | 'update_record'
  | 'create_document'
  | 'file_share'
  | 'create_case'
  | 'send_message'
  | 'send_email'
  | 'http_request'
  | 'ai_extract'
/** "automation" reacts to events; "process" is the route a form's dossiers follow. */
export type FlowKind = 'automation' | 'process'
export type Branch =
  | 'true'
  | 'false'
  | 'approve'
  | 'return'
  | 'reject'
  | 'completed'
  | 'cancelled'
  | 'submitted'
  | 'overdue'
  | 'done'
  | 'timeout'
  | 'success'
  | 'error'
  | 'default'
  // A switch names its exits by position; the label comes from its own configuration.
  | `case_${number}`

/** Query results and refs are reactive proxies, which structuredClone refuses. */
export function plainCopy<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

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
  /** Position(s) of this step on the dossier's journey, 1 = first; a step done twice has two. */
  order?: number[]
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
  group: 'Kích hoạt' | 'Logic' | 'Hành động' | 'Bước cần người' | 'Dữ liệu và tài liệu'
  hint: string
  icon: Component
  color: string
  defaults: () => Record<string, unknown>
  /** Only offered when drawing a dossier's process. */
  process?: true
  /** Settles the dossier; nothing follows it. */
  terminal?: true
  /** Only appears in a run, where a sub-process is drawn out; nobody draws it. */
  hidden?: true
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
    group: 'Bước cần người',
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
    group: 'Bước cần người',
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
    group: 'Bước cần người',
    hint: 'Giao việc, đi tiếp khi việc được nghiệm thu',
    icon: ClipboardCheck,
    color: '#2f6fb0',
    process: true,
    defaults: () => ({ title: 'Thẩm định hồ sơ: {title}', priority: 'normal', due_in_days: 3 }),
  },
  input: {
    title: 'Nhập thông tin',
    group: 'Bước cần người',
    hint: 'Một người điền thêm dữ liệu, tệp cho hồ sơ',
    icon: TextCursorInput,
    color: '#0e7c86',
    process: true,
    defaults: () => ({
      resolver: 'owner',
      fields: [{ key: 'thong_tin', label: 'Thông tin bổ sung', type: 'text', required: true, options: [] }],
      allow_files: false,
      due_in_days: 3,
      instructions: '',
    }),
  },
  subprocess: {
    title: 'Quy trình con',
    group: 'Bước cần người',
    hint: 'Chạy một quy trình đã phát hành tại đây',
    icon: Workflow,
    color: '#5a4fb0',
    process: true,
    defaults: () => ({ process_id: null }),
  },
  acknowledge: {
    title: 'Xác nhận đã đọc',
    group: 'Bước cần người',
    hint: 'Nhiều người xác nhận đã đọc',
    icon: BookCheck,
    color: '#2a8f8a',
    process: true,
    defaults: () => ({ resolver: 'users', user_ids: [], mode: 'all', due_in_days: 3, instructions: '' }),
  },
  switch: {
    title: 'Rẽ nhiều nhánh',
    group: 'Logic',
    hint: 'Chọn nhánh theo giá trị',
    icon: Split,
    color: '#7a5cd6',
    defaults: () => ({ field: '', cases: [{ label: 'Nhánh 1', operator: 'eq', value: '' }] }),
  },
  parallel: {
    title: 'Chạy song song',
    group: 'Logic',
    hint: 'Nhiều nhánh cùng chạy',
    icon: Columns3,
    color: '#7a5cd6',
    defaults: () => ({}),
  },
  join: {
    title: 'Chờ đủ nhánh',
    group: 'Logic',
    hint: 'Gom các nhánh rồi đi tiếp',
    icon: Merge,
    color: '#7a5cd6',
    process: true,
    defaults: () => ({ mode: 'all' }),
  },
  wait_until: {
    title: 'Chờ đến khi',
    group: 'Logic',
    hint: 'Đến một ngày hoặc khi điều kiện đúng',
    icon: CalendarClock,
    color: '#5b6b7d',
    process: true,
    defaults: () => ({ mode: 'date', date_field: '', conditions: [], check_every_minutes: 60, timeout_days: null }),
  },
  set_value: {
    title: 'Đặt giá trị',
    group: 'Logic',
    hint: 'Gán hoặc tính một giá trị',
    icon: Calculator,
    color: '#5b6b7d',
    defaults: () => ({ name: '', value: '', operator: 'set', operand: '' }),
  },
  update_record: {
    title: 'Cập nhật hồ sơ/việc',
    group: 'Dữ liệu và tài liệu',
    hint: 'Đổi trường, độ ưu tiên, hạn',
    icon: PencilLine,
    color: '#3a7ca5',
    process: true,
    defaults: () => ({ changes: [{ field: 'priority', value: 'high' }] }),
  },
  create_document: {
    title: 'Tạo văn bản',
    group: 'Dữ liệu và tài liệu',
    hint: 'Sinh tệp Word từ dữ liệu',
    icon: FileText,
    color: '#3a7ca5',
    process: true,
    defaults: () => ({ title: '{title}', body: '', doc_kind: 'thong_bao', agency: '', attach: true }),
  },
  file_share: {
    title: 'Lưu, chia sẻ tệp',
    group: 'Dữ liệu và tài liệu',
    hint: 'Đưa vào thư mục, cấp quyền xem',
    icon: FolderInput,
    color: '#3a7ca5',
    process: true,
    defaults: () => ({ file_id: '', folder_id: null, user_ids: [] }),
  },
  create_case: {
    title: 'Tạo hồ sơ khác',
    group: 'Dữ liệu và tài liệu',
    hint: 'Mở hồ sơ nháp theo biểu mẫu khác',
    icon: FilePlus2,
    color: '#3a7ca5',
    process: true,
    defaults: () => ({ form_id: null, title: '{title}', answers: {} }),
  },
  ai_extract: {
    title: 'AI trích xuất',
    group: 'Dữ liệu và tài liệu',
    hint: 'AI đọc tài liệu, trả về trường và tóm tắt',
    icon: ScanText,
    color: '#6d4fd0',
    process: true,
    defaults: () => ({ fields: [], text: '', read_files: true }),
  },
  send_message: {
    title: 'Nhắn tin, đăng tin',
    group: 'Hành động',
    hint: 'Gửi vào hội thoại hoặc bảng tin',
    icon: MessageSquare,
    color: '#0f8e9a',
    defaults: () => ({ channel: 'chat', conversation_id: null, audience: 'organization', body: '' }),
  },
  send_email: {
    title: 'Gửi email',
    group: 'Hành động',
    hint: 'Gửi email theo nội dung mẫu',
    icon: Mail,
    color: '#0f8e9a',
    defaults: () => ({ to: '', subject: '', body: '' }),
  },
  http_request: {
    title: 'Gọi API lấy dữ liệu',
    group: 'Hành động',
    hint: 'Gọi hệ thống khác, đọc kết quả trả về',
    icon: Download,
    color: '#b5476a',
    process: true,
    defaults: () => ({ connection_id: null, method: 'GET', path: '' }),
  },
  sub_end: {
    title: 'Kết thúc quy trình con',
    group: 'Bước cần người',
    hint: 'Quy trình con đã có kết quả',
    icon: Flag,
    color: '#5a4fb0',
    process: true,
    hidden: true,
    defaults: () => ({}),
  },
  request_info: {
    title: 'Yêu cầu bổ sung',
    group: 'Bước cần người',
    hint: 'Trả hồ sơ để người tạo bổ sung',
    icon: FilePen,
    color: '#c27a1a',
    process: true,
    terminal: true,
    defaults: () => ({ message: 'Đề nghị bổ sung tài liệu cho hồ sơ.' }),
  },
  finish: {
    title: 'Kết thúc',
    group: 'Bước cần người',
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
  submitted: 'Đã nộp',
  overdue: 'Quá hạn',
  done: 'Đến lúc',
  timeout: 'Hết giờ',
  success: 'Thành công',
  error: 'Lỗi',
  default: 'Còn lại',
}
/** Colour family of a branch: carrying on, stopping, or going back for changes. */
export function tone(branch: string | null | undefined): 'good' | 'bad' | 'warn' | undefined {
  if (!branch) return undefined
  if (['return', 'overdue', 'timeout', 'default'].includes(branch)) return 'warn'
  if (branch.startsWith('case_')) return 'good'
  return ['true', 'approve', 'completed', 'submitted', 'done', 'success'].includes(branch) ? 'good' : 'bad'
}
/** Named exits of a node, in display order; an empty list means a single plain exit. */
export function outputs(kind: NodeKind, config: Record<string, unknown>): Branch[] {
  const late: Branch[] = (config.overdue as { action?: string } | undefined)?.action === 'branch' ? ['overdue'] : []
  switch (kind) {
    case 'if':
      return ['true', 'false']
    case 'approval':
      return [
        'approve',
        ...(config.allow_return === false ? [] : (['return'] as Branch[])),
        ...(config.allow_reject === false ? [] : (['reject'] as Branch[])),
        ...late,
      ]
    case 'consult':
      return ['approve', 'reject', ...late]
    case 'input':
    case 'acknowledge':
      return ['submitted', ...late]
    case 'switch':
      return [
        ...((config.cases as unknown[]) ?? []).map((_, index) => `case_${index + 1}` as Branch),
        'default',
      ]
    case 'wait_until':
      return ['done', ...(config.timeout_days ? (['timeout'] as Branch[]) : [])]
    case 'http_request':
      return ['success', 'error']
    case 'subprocess':
      return ['approve', 'return', 'reject']
    case 'assign_task':
      return ['completed', 'cancelled']
    default:
      return []
  }
}
/** Label of a branch on a given node: opinions agree or disagree rather than approve. */
export function branchLabel(kind: NodeKind, branch: Branch, config?: Record<string, unknown>) {
  if (kind === 'consult' && (branch === 'approve' || branch === 'reject'))
    return branch === 'approve' ? 'Đồng ý' : 'Không đồng ý'
  if (branch.startsWith('case_')) {
    const cases = (config?.cases as { label?: string }[]) ?? []
    return cases[Number(branch.slice(5)) - 1]?.label || branch
  }
  return BRANCH_LABELS[branch]
}

/** The name later steps read this step's result by. */
export function nodeReference(id: string, config: Record<string, unknown>) {
  return String(config.output_name || id.toLowerCase().replace(/[^a-z0-9_]/g, '_'))
}
const OUTPUTS: Partial<Record<NodeKind, Record<string, string>>> = {
  approval: { decision: 'Quyết định', decided_by: 'Người quyết định', reason: 'Lý do', file_count: 'Số tệp nộp' },
  consult: { decision: 'Kết quả ý kiến', agreed: 'Số người đồng ý', file_count: 'Số tệp nộp' },
  acknowledge: { count: 'Số người đã xác nhận', people: 'Những người đã xác nhận' },
  input: { file_count: 'Số tệp nộp' },
  assign_task: { task_id: 'Mã công việc', file_count: 'Số tệp kết quả', file_names: 'Tên các tệp kết quả' },
  switch: { choice: 'Nhánh đã chọn' },
  wait_until: { resumed_at: 'Thời điểm tiếp tục' },
  create_document: { file_id: 'Mã tệp', name: 'Tên tệp' },
  file_share: { file_id: 'Mã tệp', shared_with: 'Số người được chia sẻ', link: 'Liên kết' },
  create_case: { case_id: 'Mã hồ sơ', code: 'Số hồ sơ' },
  send_message: { message_id: 'Mã tin nhắn', post_id: 'Mã bài viết' },
  send_email: { to: 'Người nhận', queued: 'Đã xếp hàng gửi' },
  http_request: { ok: 'Thành công', status: 'Mã phản hồi', body: 'Nội dung trả về' },
  ai_extract: { summary: 'Tóm tắt' },
}
/** What a step produces for later steps, keyed the way conditions and text read it. */
export function nodeOutputs(id: string, kind: NodeKind, config: Record<string, unknown>, title = ''): Record<string, string> {
  if (kind === 'set_value') return config.name ? { [String(config.name)]: 'Giá trị đã đặt' } : {}
  const base = OUTPUTS[kind]
  if (!base) return {}
  const extra = [
    ...((config.result_fields as { key: string; label: string }[]) ?? []),
    ...((config.fields as { key: string; label: string }[]) ?? []),
  ]
  const name = nodeReference(id, config)
  const all = { ...base, ...Object.fromEntries(extra.map((field) => [field.key, field.label || field.key])) }
  return Object.fromEntries(Object.entries(all).map(([key, label]) => [`${name}.${key}`, `${title}: ${label}`]))
}
export const OUTCOMES: Record<string, string> = {
  approved: 'Đã duyệt',
  rejected: 'Từ chối',
  needs_revision: 'Yêu cầu bổ sung',
}
/** Kinds offered in the palette of a flow of this kind. */
export function paletteKinds(): NodeKind[] {
  return (Object.keys(KINDS) as NodeKind[]).filter((kind) => kind !== 'trigger' && !KINDS[kind].hidden)
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

/** Who a step asks, in words, before it has run. */
function peopleText(c: Record<string, unknown>, names: (id: string) => string, fallback: string) {
  switch (String(c.resolver ?? fallback)) {
    case 'owner':
      return 'Người tạo hồ sơ'
    case 'user':
      return c.user_id ? names(String(c.user_id)) : 'Chọn người'
    case 'users':
      return `${((c.user_ids as string[]) ?? []).length} người`
    case 'role':
      if (!c.role) return 'Chọn vai trò'
      return c.role_scope === 'organization' ? roleLabel(String(c.role)) : `${roleLabel(String(c.role))} của đơn vị`
    case 'department':
      return c.department_id ? 'Thành viên phòng ban' : 'Thành viên đơn vị'
    case 'form_field':
      return c.form_field ? `Người ghi ở “${String(c.form_field)}”` : 'Chọn trường'
    default:
      return 'Lãnh đạo đơn vị'
  }
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
    case 'input': {
      if (data.people?.length) return data.people.join(', ')
      const count = ((c.fields as unknown[]) ?? []).length
      return `${peopleText(c, names, 'owner')} nhập ${count} trường`
    }
    case 'subprocess':
      return c.process_id ? 'Chạy quy trình đã chọn' : 'Chọn quy trình con'
    case 'acknowledge':
      return data.people?.length ? data.people.join(', ') : peopleText(c, names, 'users')
    case 'switch':
      return c.field ? `Theo ${String(c.field)}` : 'Chọn trường'
    case 'parallel':
      return 'Các nhánh chạy cùng lúc'
    case 'join':
      return c.mode === 'any' ? 'Nhánh đầu tiên đến là đi tiếp' : 'Chờ đủ các nhánh'
    case 'wait_until':
      return c.mode === 'condition' ? 'Đến khi điều kiện đúng' : c.date_field ? `Đến ngày ở ${String(c.date_field)}` : 'Chọn trường ngày'
    case 'set_value':
      return c.name ? `Đặt ${String(c.name)}` : 'Đặt tên giá trị'
    case 'update_record':
      return `${((c.changes as unknown[]) ?? []).length} thay đổi`
    case 'create_document':
      return String(c.title || 'Nhập tiêu đề')
    case 'file_share':
      return String(c.file_id || 'Chọn tệp')
    case 'create_case':
      return forms.find((form) => form.id === c.form_id)?.name ?? 'Chọn biểu mẫu'
    case 'send_message':
      return c.channel === 'feed' ? 'Đăng bảng tin' : c.conversation_id ? 'Gửi vào hội thoại' : 'Chọn hội thoại'
    case 'send_email':
      return String(c.to || 'Nhập người nhận')
    case 'http_request':
      return `${String(c.method ?? 'GET')} ${String(c.path ?? '')}`.trim()
    case 'ai_extract':
      return `Lấy ${((c.fields as unknown[]) ?? []).length} trường và tóm tắt`
    case 'sub_end':
      return OUTCOMES[String(c.outcome)] ?? ''
    case 'approval': {
      if (data.people?.length) return data.people.join(', ')
      if (c.resolver && !['user', 'department_manager'].includes(String(c.resolver))) {
        const mode = c.mode === 'all' ? ' · tất cả duyệt' : c.mode === 'quorum' ? ` · cần ${c.quorum ?? '?'} người` : ''
        return peopleText(c, names, 'department_manager') + mode
      }
      const who = c.resolver === 'user' ? (c.user_id ? names(String(c.user_id)) : 'Chọn người duyệt') : 'Lãnh đạo đơn vị'
      return c.due_in_days != null ? `${who} · ${c.due_in_days} ngày` : who
    }
    case 'consult': {
      if (data.people?.length) return data.people.join(', ')
      if (c.resolver && c.resolver !== 'users') return peopleText(c, names, 'users')
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
      data: { kind: node.type, label: node.label, config: plainCopy(node.data) },
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
    // A "return" exit usually leads backwards, where right-angled lines would lie on the forward ones.
    type: handle === 'return' ? 'default' : 'smoothstep',
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

/** Someone on the board of directors decides; works as is, without picking a person. */
const BOARD = { resolver: 'role', role: 'director', role_scope: 'organization' }
/** The dossier's starting point, naming the documents it should come with. */
function startWith(documents: string[]) {
  return n('trigger', 'trigger', 0, 0, { event: 'case.submitted', form_id: null, required_documents: documents })
}
function done(id: string, x: number, y: number, message: string) {
  return step(id, 'finish', x, y, 'Hoàn tất', { result: 'approved', message })
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
    description: 'Lãnh đạo đơn vị duyệt trước; được duyệt thì chuyển ban giám đốc duyệt tiếp.',
    graph: {
      nodes: [
        start(),
        step('leader', 'approval', 320, 0, 'Lãnh đạo đơn vị duyệt'),
        step('board', 'approval', 680, -40, 'Ban giám đốc duyệt', BOARD),
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
  {
    key: 'process-urgent-track',
    title: 'Hồ sơ khẩn trình thẳng ban giám đốc',
    description:
      'Hồ sơ có mức ưu tiên Khẩn đi thẳng tới ban giám đốc; hồ sơ thường qua lãnh đạo đơn vị trước rồi mới tới ban giám đốc.',
    graph: {
      nodes: [
        start(),
        n('is_urgent', 'if', 320, 0, { mode: 'all', conditions: [{ field: 'priority', operator: 'eq', value: 'urgent' }] }),
        step('leader', 'approval', 680, 140, 'Lãnh đạo đơn vị duyệt'),
        step('board', 'approval', 1040, -60, 'Ban giám đốc duyệt', BOARD),
      ],
      edges: [
        e('trigger', 'is_urgent'),
        e('is_urgent', 'board', 'true'),
        e('is_urgent', 'leader', 'false'),
        e('leader', 'board', 'approve'),
      ],
    },
  },
  {
    key: 'process-leave',
    title: 'Nghỉ phép: trên 3 ngày cần ban giám đốc',
    description:
      'Lãnh đạo đơn vị duyệt mọi đơn; đơn nghỉ trên 3 ngày chuyển tiếp ban giám đốc. Đổi trường “so_ngay” thành trường số ngày nghỉ của biểu mẫu.',
    graph: {
      nodes: [
        startWith(['Đơn xin nghỉ phép']),
        step('leader', 'approval', 320, 0, 'Lãnh đạo đơn vị duyệt', { due_in_days: 1 }),
        n('long_leave', 'if', 680, 0, { mode: 'all', conditions: [{ field: 'form.so_ngay', operator: 'gt', value: 3 }] }),
        step('board', 'approval', 1040, -80, 'Ban giám đốc duyệt', { ...BOARD, due_in_days: 1 }),
        done('short_ok', 1040, 120, 'Đơn nghỉ từ 3 ngày trở xuống, lãnh đạo đơn vị duyệt là đủ.'),
      ],
      edges: [
        e('trigger', 'leader'),
        e('leader', 'long_leave', 'approve'),
        e('long_leave', 'board', 'true'),
        e('long_leave', 'short_ok', 'false'),
      ],
    },
  },
  {
    key: 'process-procurement-value',
    title: 'Mua sắm theo giá trị',
    description:
      'Lãnh đạo đơn vị duyệt; từ 50 triệu trở lên thì xin ý kiến kế toán, hành chính rồi ban giám đốc quyết. Đổi trường “so_tien” theo biểu mẫu và chọn người cho ý kiến.',
    graph: {
      nodes: [
        startWith(['Tờ trình mua sắm', 'Báo giá của nhà cung cấp']),
        step('leader', 'approval', 320, 0, 'Lãnh đạo đơn vị duyệt'),
        n('big', 'if', 680, 0, { mode: 'all', conditions: [{ field: 'form.so_tien', operator: 'gte', value: 50000000 }] }),
        step('opinions', 'consult', 1040, -100, 'Kế toán, hành chính cho ý kiến'),
        step('board', 'approval', 1400, -100, 'Ban giám đốc quyết định', BOARD),
        done('small_ok', 1040, 140, 'Dưới 50 triệu: lãnh đạo đơn vị duyệt là đủ.'),
      ],
      edges: [
        e('trigger', 'leader'),
        e('leader', 'big', 'approve'),
        e('big', 'opinions', 'true'),
        e('big', 'small_ok', 'false'),
        e('opinions', 'board', 'approve'),
        e('opinions', 'board', 'reject'),
      ],
    },
  },
  {
    key: 'process-business-trip',
    title: 'Đi công tác và tạm ứng',
    description:
      'Lãnh đạo đơn vị rồi ban giám đốc duyệt; xong thì giao kế toán chuyển tạm ứng, nộp phiếu chi mới hoàn tất. Chọn người nhận việc kế toán.',
    graph: {
      nodes: [
        startWith(['Kế hoạch công tác', 'Dự toán chi phí']),
        step('leader', 'approval', 320, 0, 'Lãnh đạo đơn vị duyệt'),
        step('board', 'approval', 680, 0, 'Ban giám đốc duyệt', BOARD),
        step('advance', 'assign_task', 1040, 0, 'Kế toán chuyển tạm ứng', {
          title: 'Chuyển tạm ứng công tác: {title}',
          due_in_days: 2,
          require_files: 1,
          required_documents: ['Phiếu chi'],
        }),
        done('paid', 1400, -60, 'Đã duyệt và chuyển tạm ứng.'),
      ],
      edges: [
        e('trigger', 'leader'),
        e('leader', 'board', 'approve'),
        e('board', 'advance', 'approve'),
        e('advance', 'paid', 'completed'),
      ],
    },
  },
  {
    key: 'process-incoming-doc',
    title: 'Xử lý công văn đến',
    description:
      'Văn thư vào sổ (số đến, ngày đến), ban giám đốc ghi ý kiến chỉ đạo, rồi giao đơn vị xử lý. Chọn người hoặc phòng xử lý ở bước giao việc.',
    graph: {
      nodes: [
        startWith(['Bản chụp công văn đến']),
        step('register', 'input', 320, 0, 'Văn thư vào sổ', {
          resolver: 'owner',
          due_in_days: 1,
          fields: [
            { key: 'so_den', label: 'Số đến', type: 'text', required: true, options: [] },
            { key: 'ngay_den', label: 'Ngày đến', type: 'date', required: true, options: [] },
          ],
        }),
        step('direct', 'approval', 680, 0, 'Ban giám đốc cho ý kiến chỉ đạo', {
          ...BOARD,
          due_in_days: 1,
          allow_reject: false,
          instructions: 'Ghi ý kiến chỉ đạo vào ô lý do; đơn vị xử lý sẽ đọc được.',
        }),
        step('handle', 'assign_task', 1040, 0, 'Đơn vị xử lý công văn', {
          title: 'Xử lý công văn: {title}',
          due_in_days: 5,
        }),
        done('closed', 1400, -60, 'Công văn đã được xử lý.'),
      ],
      edges: [
        e('trigger', 'register'),
        e('register', 'direct', 'submitted'),
        e('direct', 'handle', 'approve'),
        e('handle', 'closed', 'completed'),
      ],
    },
  },
  {
    key: 'process-outgoing-doc',
    title: 'Trình ký văn bản đi',
    description:
      'Lãnh đạo đơn vị kiểm tra nội dung, ban giám đốc ký duyệt, văn thư vào số, đóng dấu và phát hành rồi báo người soạn.',
    graph: {
      nodes: [
        startWith(['Dự thảo văn bản']),
        step('review', 'approval', 320, 0, 'Lãnh đạo đơn vị kiểm tra nội dung'),
        step('sign', 'approval', 680, 0, 'Ban giám đốc ký duyệt', BOARD),
        step('issue', 'assign_task', 1040, 0, 'Văn thư phát hành', {
          title: 'Vào số, đóng dấu, phát hành: {title}',
          due_in_days: 1,
          require_files: 1,
          required_documents: ['Bản đã ký, đóng dấu'],
        }),
        n('tell_owner', 'notify', 1400, -60, { recipients: ['owner'], title: 'Văn bản đã được phát hành: {title}' }),
        done('issued', 1760, -60, 'Văn bản đã ký và phát hành.'),
      ],
      edges: [
        e('trigger', 'review'),
        e('review', 'sign', 'approve'),
        e('sign', 'issue', 'approve'),
        e('issue', 'tell_owner', 'completed'),
        e('tell_owner', 'issued'),
      ],
    },
  },
  {
    key: 'process-contract',
    title: 'Rà soát hợp đồng song song rồi ký',
    description:
      'Pháp chế và kế toán rà soát cùng lúc; cả hai đồng ý thì ban giám đốc ký. Một bên trả lại hay từ chối thì hồ sơ dừng ở đó. Chọn người rà soát ở hai bước.',
    graph: {
      nodes: [
        startWith(['Dự thảo hợp đồng', 'Hồ sơ năng lực đối tác']),
        n('split', 'parallel', 320, 0, {}),
        step('legal', 'approval', 640, -120, 'Pháp chế rà soát', { resolver: 'user' }),
        step('finance', 'approval', 640, 120, 'Kế toán rà soát', { resolver: 'user' }),
        n('both', 'join', 1000, 0, { mode: 'all' }),
        step('sign', 'approval', 1320, 0, 'Ban giám đốc ký hợp đồng', BOARD),
      ],
      edges: [
        e('trigger', 'split'),
        e('split', 'legal'),
        e('split', 'finance'),
        e('legal', 'both', 'approve'),
        e('finance', 'both', 'approve'),
        e('both', 'sign'),
      ],
    },
  },
  {
    key: 'process-payment',
    title: 'Thanh toán theo chứng từ',
    description:
      'Kế toán kiểm tra chứng từ, ban giám đốc duyệt chi, kế toán chi trả và nộp ủy nhiệm chi, người đề nghị được báo. Chọn kế toán ở bước đầu và bước chi trả.',
    graph: {
      nodes: [
        startWith(['Giấy đề nghị thanh toán', 'Hóa đơn', 'Biên bản nghiệm thu']),
        step('check', 'approval', 320, 0, 'Kế toán kiểm tra chứng từ', { resolver: 'user', due_in_days: 2 }),
        step('board', 'approval', 680, 0, 'Ban giám đốc duyệt chi', BOARD),
        step('pay', 'assign_task', 1040, 0, 'Kế toán chi trả', {
          title: 'Chi trả: {title}',
          due_in_days: 2,
          require_files: 1,
          required_documents: ['Ủy nhiệm chi'],
        }),
        n('tell_owner', 'notify', 1400, -60, { recipients: ['owner'], title: 'Đã chi trả: {title}' }),
        done('paid', 1760, -60, 'Đã duyệt chi và chi trả.'),
      ],
      edges: [
        e('trigger', 'check'),
        e('check', 'board', 'approve'),
        e('board', 'pay', 'approve'),
        e('pay', 'tell_owner', 'completed'),
        e('tell_owner', 'paid'),
      ],
    },
  },
  {
    key: 'process-repair',
    title: 'Sửa chữa tài sản, thiết bị',
    description:
      'Lãnh đạo đơn vị xác nhận, giao kiểm tra hiện trạng kèm biên bản, ban giám đốc duyệt kinh phí, rồi giao sửa chữa và nghiệm thu.',
    graph: {
      nodes: [
        startWith(['Ảnh hiện trạng tài sản']),
        step('leader', 'approval', 320, 0, 'Lãnh đạo đơn vị xác nhận'),
        step('inspect', 'assign_task', 680, 0, 'Kiểm tra hiện trạng', {
          title: 'Kiểm tra hiện trạng: {title}',
          due_in_days: 2,
          require_files: 1,
          required_documents: ['Biên bản kiểm tra hiện trạng'],
        }),
        step('budget', 'approval', 1040, 0, 'Ban giám đốc duyệt kinh phí', BOARD),
        step('repair', 'assign_task', 1400, 0, 'Sửa chữa và nghiệm thu', {
          title: 'Sửa chữa: {title}',
          due_in_days: 7,
          require_files: 1,
          required_documents: ['Biên bản nghiệm thu'],
        }),
        done('fixed', 1760, -60, 'Đã sửa chữa và nghiệm thu.'),
      ],
      edges: [
        e('trigger', 'leader'),
        e('leader', 'inspect', 'approve'),
        e('inspect', 'budget', 'completed'),
        e('budget', 'repair', 'approve'),
        e('repair', 'fixed', 'completed'),
      ],
    },
  },
  {
    key: 'process-recruitment',
    title: 'Đề xuất tuyển dụng',
    description:
      'Lãnh đạo đơn vị đề xuất, phòng tổ chức – hành chính cho ý kiến về biên chế và kinh phí, ban giám đốc quyết định. Chọn người cho ý kiến.',
    graph: {
      nodes: [
        startWith(['Bản mô tả vị trí việc làm']),
        step('leader', 'approval', 320, 0, 'Lãnh đạo đơn vị đề xuất'),
        step('hr', 'consult', 680, 0, 'Tổ chức – hành chính cho ý kiến'),
        step('board', 'approval', 1040, 0, 'Ban giám đốc quyết định', BOARD),
      ],
      edges: [
        e('trigger', 'leader'),
        e('leader', 'hr', 'approve'),
        e('hr', 'board', 'approve'),
        e('hr', 'board', 'reject'),
      ],
    },
  },
  {
    key: 'process-announce',
    title: 'Ban hành quy định, cả đơn vị xác nhận đã đọc',
    description:
      'Ban giám đốc duyệt ban hành; sau đó mọi người trong đơn vị của hồ sơ xác nhận đã đọc, đủ người thì hoàn tất.',
    graph: {
      nodes: [
        startWith(['Dự thảo quy định']),
        step('board', 'approval', 320, 0, 'Ban giám đốc duyệt ban hành', BOARD),
        step('read', 'acknowledge', 680, 0, 'Cả đơn vị xác nhận đã đọc', {
          resolver: 'department',
          department_id: null,
          due_in_days: 5,
        }),
        done('published', 1040, 0, 'Đã ban hành và phổ biến.'),
      ],
      edges: [e('trigger', 'board'), e('board', 'read', 'approve'), e('read', 'published', 'submitted')],
    },
  },
  {
    key: 'process-escalate',
    title: 'Quá hạn duyệt thì chuyển cấp trên',
    description:
      'Lãnh đạo đơn vị có 2 ngày để duyệt; quá hạn chưa ai xử lý thì hồ sơ tự chuyển lên ban giám đốc.',
    graph: {
      nodes: [
        start(),
        step('leader', 'approval', 320, 0, 'Lãnh đạo đơn vị duyệt', { due_in_days: 2, overdue: { action: 'branch' } }),
        step('board', 'approval', 720, 120, 'Ban giám đốc duyệt thay', BOARD),
      ],
      edges: [e('trigger', 'leader'), e('leader', 'board', 'overdue')],
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
  /** Asked again after the dossier was sent back; the earlier answers are superseded. */
  attempt?: number
  superseded?: boolean
}
/** Paint a run on the canvas: each node gets its state, each taken edge lights up. */
export function paintRun(nodes: Node<FlowNodeData>[], edges: Edge[], steps: RunStep[]) {
  const byNode = new Map(steps.filter((s) => s.node_id && !s.superseded).map((s) => [s.node_id!, s]))
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
          message: [step?.attempt ? `Lần ${step.attempt}` : '', step?.message ?? (step?.title ? `“${step.title}”` : '')]
            .filter(Boolean)
            .join(' · ') || undefined,
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
