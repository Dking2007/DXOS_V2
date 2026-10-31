// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
import type { ApprovalStep, Condition, FormField } from '@dx/web-shared/types.ts'

export interface PackageVersion {
  id: string
  package_id: string
  form_id: string
  version_no: number
  approval_steps: ApprovalStep[]
  required_file_count: number
  state: 'draft' | 'validated' | 'published' | string
  revision: number
  config_hash: string
  created_at: string
}
export interface RoutingEvidence {
  label: string
  condition: Condition | null
  selected: boolean
  recipient: string | null
  evaluated_value: unknown
}
export interface Preview {
  path: string[]
  state: string
  assignees: { node_id: string; subject: string }[]
  routing_evidence: RoutingEvidence[]
}
export type Decision = 'approve' | 'return' | 'reject'
export type ErrorCode =
  | 'required_documents_missing'
  | 'approval_configuration_error'
  | 'form_validation_error'
  | 'self_approval_denied'
export interface Fixture {
  name: string
  payload: Record<string, unknown>
  decisions: Record<string, { decision: Decision }>
  file_count: number
  expected_path: string[]
  expected_error_code: ErrorCode | null
}
export interface Suite {
  id: string
  config_hash: string
  cases: Fixture[]
  created_at: string
}
export interface ReportResult {
  name: string
  passed: boolean
  expected_path?: string[]
  actual_path?: string[]
  error?: { code: string; detail: string }
}
export interface Report {
  id: string
  suite_id: string
  config_hash: string
  passed: boolean
  results: ReportResult[]
  created_at: string
}

export const VERSION_STATE: Record<string, string> = {
  draft: 'Bản nháp',
  validated: 'Đã kiểm tra',
  published: 'Đang dùng',
}
export const ERROR_LABEL: Record<ErrorCode, string> = {
  required_documents_missing: 'Thiếu tài liệu bắt buộc',
  approval_configuration_error: 'Không tìm được người duyệt',
  form_validation_error: 'Dữ liệu biểu mẫu không hợp lệ',
  self_approval_denied: 'Người tạo trùng người duyệt',
}
export interface ImpactSide {
  state: string
  path: string[]
  assignees: string[]
  routing_evidence?: RoutingEvidence[]
  error?: { code: string; detail: string }
}
export interface ImpactItem {
  name: string
  changed: boolean
  changes: ('outcome' | 'path' | 'assignees')[]
  causes: string[]
  baseline: ImpactSide
  candidate: ImpactSide
  recipient_drift: { recorded: string[]; now: string[] } | null
}
export interface Impact {
  baseline: { id: string; version_no: number }
  candidate: { id: string; version_no: number }
  differences: { rules: boolean; form: boolean; required_files: boolean }
  summary: { fixtures: number; changed: number; recipient_drift: number }
  items: ImpactItem[]
}
export const CHANGE_LABEL = { outcome: 'kết quả', path: 'đường đi', assignees: 'người nhận' } as const
/** The approvers a fixture would meet, as the labels of the steps it passes through. */
export function routeLabels(side: ImpactSide): string {
  if (side.error) return ERROR_LABEL[side.error.code as ErrorCode] ?? side.error.detail
  const steps = (side.routing_evidence ?? []).filter((step) => step.selected).map((step) => step.label)
  return steps.length ? steps.join(' → ') : 'Không có bước duyệt'
}
export function impactHeadline(impact: Impact): string {
  const { fixtures, changed } = impact.summary
  if (!fixtures) return 'Bộ thử chưa có hồ sơ mẫu nào.'
  if (!changed) return `Cả ${fixtures} hồ sơ mẫu cho kết quả giống phiên bản trước.`
  return `${changed}/${fixtures} hồ sơ mẫu thay đổi so với phiên bản trước.`
}
export const DECISION_LABEL: Record<Decision, string> = {
  approve: 'Duyệt',
  return: 'Trả lại',
  reject: 'Từ chối',
}
export const ROLE_LABEL: Record<string, string> = {
  staff: 'Cán bộ / nhân viên',
  manager: 'Lãnh đạo phòng',
  director: 'Ban giám đốc',
  technical_admin: 'Quản trị kỹ thuật',
}
const OPERATOR: Record<string, string> = { eq: '=', ne: '≠', gt: '>', gte: '≥', lt: '<', lte: '≤' }

export function formatValue(value: unknown): string {
  if (typeof value === 'number') return value.toLocaleString('vi-VN')
  if (typeof value === 'boolean') return value ? 'Có' : 'Không'
  if (value === null || value === undefined || value === '') return 'trống'
  return String(value)
}

/** "Kinh phí > 50.000.000" using the form's field label rather than its key. */
export function conditionText(condition: Condition, fields: FormField[]): string {
  const label = fields.find((field) => field.key === condition.field)?.label ?? condition.field
  return `${label} ${OPERATOR[condition.operator] ?? condition.operator} ${formatValue(condition.value)}`
}

export function resolverText(step: ApprovalStep, userName: (id: string) => string): string {
  return step.resolver === 'department_manager'
    ? 'Lãnh đạo phòng của người trình'
    : step.user_id
      ? userName(step.user_id)
      : 'Chưa chọn người duyệt'
}

export interface PathStop {
  id: string
  label: string
  kind: 'start' | 'review' | 'end'
}
/**
 * The engine's node ids as people read them. `review_i` is the i-th step that applied to the
 * case (conditions may skip some), so its label comes from the selected steps in order;
 * `continue_i` gates are plumbing and are left out.
 */
export function pathStops(path: string[], selectedLabels: string[]): PathStop[] {
  const stops: PathStop[] = []
  for (const id of path) {
    if (id === 'start') stops.push({ id, label: 'Bắt đầu', kind: 'start' })
    else if (id === 'end') stops.push({ id, label: 'Hoàn tất', kind: 'end' })
    else if (id.startsWith('review_')) {
      const index = Number(id.slice('review_'.length))
      stops.push({ id, label: selectedLabels[index] ?? `Lượt duyệt ${index + 1}`, kind: 'review' })
    }
  }
  return stops
}

/** Simulated decisions keyed the way the engine names approval nodes: review_0, review_1… */
export function decisionsFor(choices: Decision[]): Record<string, { decision: Decision }> {
  return Object.fromEntries(choices.map((decision, index) => [`review_${index}`, { decision }]))
}
export function choicesFrom(decisions: Record<string, { decision: Decision }>, count: number): Decision[] {
  return Array.from({ length: count }, (_, index) => decisions[`review_${index}`]?.decision ?? 'approve')
}

/** The newest report of each suite that was run against the given configuration. */
export function latestReports(reports: Report[], configHash: string): Map<string, Report> {
  const latest = new Map<string, Report>()
  for (const report of [...reports].sort((a, b) => b.created_at.localeCompare(a.created_at))) {
    if (report.config_hash === configHash && !latest.has(report.suite_id)) latest.set(report.suite_id, report)
  }
  return latest
}

export interface Readiness {
  validated: boolean
  hasSuites: boolean
  allPassed: boolean
  canPublish: boolean
  /** Why publishing is not yet possible, in the order it should be fixed. */
  blocker: string | null
}
export function readiness(version: PackageVersion, suites: Suite[], reports: Report[]): Readiness {
  const current = suites.filter((suite) => suite.config_hash === version.config_hash)
  const latest = latestReports(reports, version.config_hash)
  const validated = version.state === 'validated' || version.state === 'published'
  const hasSuites = current.length > 0
  // Test sets are optional; the ones that exist must pass on their latest run.
  const allPassed = current.every((suite) => latest.get(suite.id)?.passed)
  let blocker: string | null = null
  if (version.state === 'published') blocker = null
  else if (!validated) blocker = 'Kiểm tra cấu hình trước.'
  else if (!allPassed) blocker = 'Chạy lại cho tới khi mọi bộ kịch bản đều đạt.'
  return { validated, hasSuites, allPassed, canPublish: version.state === 'validated' && allPassed, blocker }
}
