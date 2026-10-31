// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
export type FieldType =
  'text' | 'textarea' | 'number' | 'date' | 'select' | 'checkbox'
export interface FormField {
  key: string
  label: string
  type: FieldType
  required?: boolean
  options?: string[]
}
export interface Condition {
  field: string
  operator: 'eq' | 'ne' | 'gt' | 'gte' | 'lt' | 'lte'
  value: string | number | boolean
}
export interface ApprovalStep {
  label: string
  resolver: 'user' | 'department_manager'
  user_id?: string
  condition?: Condition
  /** How long the approver has once the dossier reaches this step; empty means no deadline. */
  due_hours?: number | null
}
export interface FormTemplate {
  id: string
  name: string
  description?: string
  fields: FormField[]
  approval_steps: ApprovalStep[]
  revision?: number
  version?: number
  schema_version?: number
  state?: string
}
export interface User {
  id: string
  subject: string
  display_name: string
  department_id?: string | null
  role?: string
  roles?: string[]
  csrf_token?: string
  capabilities?: string[]
}
export interface Department {
  id: string
  name: string
  code?: string
  parent_id?: string | null
  manager_id?: string | null
  revision?: number
}
export interface DriveFile {
  id: string
  name: string
  folder_id?: string | null
  core_file_id?: string
  revision: number
  size?: number
  mime?: string
  created_at?: string
  updated_at?: string
  trashed?: boolean
  deleted_at?: string | null
  owner_id?: string
  current_version_id?: string
  labels?: string[]
}
export interface Folder {
  id: string
  name: string
  parent_id?: string | null
  revision?: number
  owner_id?: string
  deleted_at?: string | null
  acl_state?: string
}
export interface Share {
  id: string
  resource_type: string
  resource_id: string
  user_id: string
  access: string
}
export interface FileVersion {
  id: string
  version_no: number
  size?: number
  checksum?: string
  created_at?: string
  mime?: string
}
export interface CaseItem {
  id: string
  code: string
  title: string
  status: string
  revision: number
  form_id: string
  owner_id?: string
  owner_name?: string
  creator_id?: string
  created_by?: string
  created_at?: string
  updated_at?: string
  payload?: Record<string, unknown>
  payload_revision?: number
  file_ids?: string[]
  /** How many times it was submitted; 0 means a draft nobody has seen, which may be deleted. */
  submission_no?: number
  archived_at?: string | null
}
export interface Submission {
  id: string
  number: number
  created_at?: string
  submitted_at?: string
  payload_snapshot?: Record<string, unknown>
  payload_revision?: number
  state?: string
  files_snapshot?: {
    id?: string
    file_id?: string
    name?: string
    version_id?: string
    core_version_id?: string
    checksum?: string
  }[]
}
export interface ApprovalTask {
  id: string
  case_id: string
  /** From the step's deadline, set when the step reached its approver. */
  due_at?: string | null
  case_title?: string
  case_code?: string
  case_number?: string
  label?: string
  step_label?: string
  assignee_id: string
  assignee_name?: string
  status?: string
  state?: string
  revision: number
  created_at?: string
  decided_at?: string
  decision?: string
  reason?: string
  sequence?: number
  step_index?: number
  on_behalf_of?: string | null
  decided_by_id?: string | null
  decided_by_name?: string
}
export interface HistoryEvent {
  id?: string
  action: string
  actor_id?: string
  created_at?: string
  detail?: string | Record<string, unknown>
  data?: Record<string, unknown>
}
export interface CaseDetail extends CaseItem {
  form: FormTemplate
  payload: Record<string, unknown>
  submissions: Submission[]
  approval_tasks: ApprovalTask[]
  history: HistoryEvent[]
  files?: DriveFile[]
}
export interface Notification {
  id: string
  title: string
  body?: string
  created_at: string
  read_at?: string | null
  resource_id?: string
  case_id?: string
  link?: string | null
  category?: 'approval' | 'task' | 'mention' | 'feed' | 'automation' | 'other'
}
export interface AgendaItem {
  kind: 'task' | 'approval' | 'mention'
  id: string
  title: string
  action: 'accept' | 'open' | 'assign' | 'review' | 'decide'
  link: string
  due_at: string | null
  overdue: boolean
  detail: string
  status: string | null
}
export interface MeOverview {
  counts: {
    tasks: number
    tasks_to_review: number
    approvals: number
    notifications: number
    chat: number
  }
  agenda: AgendaItem[]
  as_of: string
}
export type TaskStatus =
  | 'draft'
  | 'assigned'
  | 'accepted'
  | 'in_progress'
  | 'blocked'
  | 'submitted'
  | 'returned'
  | 'completed'
  | 'cancelled'
export type TaskAction =
  | 'accept'
  | 'start'
  | 'submit'
  | 'complete'
  | 'return'
  | 'block'
  | 'unblock'
  | 'cancel'
  | 'assign'
export interface ChecklistItem {
  id?: string
  text: string
  done: boolean
}
export interface Task {
  id: string
  title: string
  description: string
  creator_id: string
  creator_name: string
  department_id: string | null
  department_name: string
  assignee_id: string | null
  assignee_name: string
  watcher_ids: string[]
  priority: 'low' | 'normal' | 'high' | 'urgent'
  due_at: string | null
  status: TaskStatus
  checklist: ChecklistItem[]
  checklist_done: number
  checklist_total: number
  parent_id: string | null
  labels: string[]
  file_ids: string[]
  case_id: string | null
  source: { type: string; id?: string | null; label?: string }
  result: string
  revision: number
  overdue: boolean
  actions: TaskAction[]
  created_at: string
  updated_at: string
  completed_at: string | null
}
export interface TaskDetail extends Task {
  watchers: { id: string; display_name: string }[]
  events: {
    id: string
    action: string
    actor_name: string
    detail: Record<string, unknown>
    created_at: string
  }[]
  comments: { id: string; author_name: string; body: string; created_at: string }[]
  subtasks: { id: string; title: string; status: TaskStatus; assignee_name: string }[]
  parent: { id: string; title: string } | null
  case: { id: string; title: string; code: string } | null
  files: { id: string; name: string | null; size?: number; restricted?: boolean }[]
}
export interface ChatMessage {
  id: string
  conversation_id: string
  seq: number
  sender_id: string
  sender_name: string
  body: string
  mine: boolean
  deleted: boolean
  edited_at: string | null
  created_at: string
  reactions: Record<string, string[]>
  mentions: string[]
  reply_to?: { id: string; seq: number; body: string; sender_name: string } | null
  attachments: ChatAttachment[]
}
export interface ChatAttachment {
  id: string
  name: string
  mime: string
  size: number
  kind: 'image' | 'video' | 'audio' | 'file'
  /** Served by Workspace after checking conversation membership on every request. */
  url: string
}
export interface Conversation {
  id: string
  kind: 'direct' | 'group' | 'department' | 'task' | 'case'
  title: string
  ref_type: string | null
  ref_id: string | null
  last_seq: number
  unread: number
  my_role: string
  member_count: number
  updated_at: string
  last_message: ChatMessage | null
  members?: { user_id: string; display_name: string; role: string; last_read_seq: number }[]
}
export interface Post {
  id: string
  author_id: string
  author_name: string
  body: string
  audience: 'organization' | 'department'
  department_name: string
  official: boolean
  pinned_at: string | null
  reactions: Record<string, number>
  my_reaction: string | null
  comment_count: number
  saved: boolean
  can_edit: boolean
  can_moderate: boolean
  revision: number
  created_at: string
  attachments?: PostMedia[]
}
export interface PostMedia {
  id: string
  name: string
  mime: string
  size: number
  kind: 'image' | 'video'
  url: string
  /** Text alternative for screen readers, written by the author or drafted by AI. */
  alt?: string | null
}
export interface PostComment {
  id: string
  author_name: string
  body: string
  created_at: string
  can_delete: boolean
}
export interface AssistantStatus {
  enabled: boolean
  ready: boolean
  welcome: string
  suggestions: string[]
  provider: string | null
  remaining: number | null
  daily_limit: number
  can_manage: boolean
}
export interface AssistantSource {
  n: number
  id: string
  title: string
  category: string
}
export interface AssistantReply {
  answer: string
  truncated: boolean
  sources: AssistantSource[]
  remaining: number | null
}
export interface AssistantProvider {
  id: string
  name: string
  kind:
    | 'anthropic'
    | 'openai'
    | 'gemini'
    | 'deepseek'
    | 'custom_anthropic'
    | 'custom_chat'
    | 'custom_responses'
    | 'ollama'
    | 'vllm'
  kind_label: string
  model: string
  base_url: string | null
  endpoint: string | null
  key_hint: string
  max_output_tokens: number
  active: boolean
  last_test_ok: boolean | null
  last_test_at: string | null
  revision: number
  updated_at: string
}
export interface AssistantArticle {
  id: string
  title: string
  category: 'process' | 'guide' | 'faq' | 'other'
  category_label: string
  published: boolean
  source: 'manual' | 'package'
  source_ref: string | null
  revision: number
  updated_at: string
  excerpt: string
  length: number
  body?: string
}
export interface AssistantAdmin {
  config: {
    enabled: boolean
    welcome: string
    instructions: string
    suggestions: string[]
    daily_limit: number
    revision: number
  }
  providers: AssistantProvider[]
  kinds: {
    kind: AssistantProvider['kind']
    label: string
    suggested_model: string
    custom?: boolean
    /** A model server the office runs itself (Ollama, vLLM). */
    self_hosted?: boolean
    key_optional?: boolean
    default_base_url?: string
  }[]
  /** Hosts the operator allowed for plain HTTP or private addresses (ASSISTANT_ALLOWED_HOSTS). */
  allowed_hosts: string[]
  categories: { key: AssistantArticle['category']; label: string }[]
  article_count: number
  published_count: number
}
