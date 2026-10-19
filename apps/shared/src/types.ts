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
}
