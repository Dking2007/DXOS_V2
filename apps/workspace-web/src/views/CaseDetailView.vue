<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import {
  Archive,
  ArchiveRestore,
  ArrowLeft,
  Ban,
  Check,
  CheckCheck,
  ClipboardCheck,
  Download,
  Eye,
  FileText,
  GitBranch,
  History,
  Info,
  ListPlus,
  MessagesSquare,
  Paperclip,
  Pencil,
  Plus,
  RotateCcw,
  Save,
  Undo2,
  Send,
  ShieldCheck,
  Sparkles,
  Trash2,
  XCircle,
} from 'lucide-vue-next'
import { api } from '../api'
import { useSession } from '../stores/session'
import {
  ApiError,
  errorText,
  formatDate,
  newIntent,
} from '@dx/web-shared/api.ts'
import type { Page } from '@dx/web-shared/api.ts'
import type {
  ApprovalTask,
  CaseDetail,
  Conversation,
  Task,
  DriveFile,
  HistoryEvent,
  User,
} from '@dx/web-shared/types.ts'
import type { components } from '@dx/web-shared/generated/workspace-api.ts'
import { validatePayload } from '@dx/web-shared/forms.ts'
import StatePanel from '@dx/web-shared/components/StatePanel.vue'
import StatusBadge from '@dx/web-shared/components/StatusBadge.vue'
import ModalDialog from '@dx/web-shared/components/ModalDialog.vue'
import SchemaForm from '@dx/web-shared/components/SchemaForm.vue'
import TaskCreateDialog from '../components/TaskCreateDialog.vue'
import CaseAiPanel from '../ai/CaseAiPanel.vue'
import { useAi } from '../ai/useAi'
import { OPERATORS } from '../flow/nodes'
import { toast } from '../ui/toast'
import { previewKind } from '../ui/preview'
import FilePreview from '../components/FilePreview.vue'
import { useUnsavedGuard } from '../ui/unsaved'
const route = useRoute()
const router = useRouter()
const queryClient = useQueryClient()
const session = useSession()
const id = String(route.params.id)
const detail = useQuery({
  queryKey: ['case', id],
  queryFn: () => api.request<CaseDetail>(`/cases/${id}`),
  refetchInterval: (query) =>
    ['pending_workflow_start', 'submitted', 'processing'].includes(
      query.state.data?.status ?? '',
    )
      ? 10_000
      : false,
})
interface CaseExplanation {
  submissions: {
    submission_id: string
    number: number
    package_version_id: string | null
    payload_revision: number
    routing_evidence: {
      label: string
      selected: boolean
      recipient: string | null
      condition: { field: string; operator: string; value: unknown } | null
      evaluated_value: unknown
    }[]
    decision_traces: {
      node_id: string
      expression: { path: string; operator: string; value: unknown }
      evaluated_inputs: Record<string, unknown>
      result: boolean
      selected_edges: string[]
    }[]
  }[]
}
const explanation = useQuery({
  queryKey: ['case-explanation', id],
  queryFn: () => api.request<CaseExplanation>(`/cases/${id}/explanation`),
  enabled: computed(() => !!detail.data.value?.submissions.length),
})
interface FieldEvidence {
  id: string
  field_key: string
  source_file_id: string
  source_version_id: string
  source_page: number
  source_quote: string
  suggested_value: { value: unknown }
  confirmed_value: { value: unknown } | null
  review_state: string
  source_kind: string
  provenance: { extraction_job_id?: string; ai_profile_version?: string }
  reviewed_by_id: string | null
  revision: number
}
const fieldEvidence = useQuery({
  queryKey: ['field-evidence', id],
  queryFn: () => api.request<Page<FieldEvidence>>(`/cases/${id}/field-evidence`),
})
// The manual form is rarely needed now that AI proposes evidence; it stays one click away.
const manualEvidence = ref(false)
const evidenceField = ref('')
const evidenceFile = ref('')
const evidencePage = ref(1)
const evidenceQuote = ref('')
const evidenceValue = ref('')
const correctedValues = ref<Record<string, string>>({})
async function addEvidence() {
  busy.value = true
  error.value = null
  try {
    await api.request(`/cases/${id}/field-evidence`, {
      method: 'POST', headers: { 'Idempotency-Key': newIntent() },
      body: JSON.stringify({ field_key: evidenceField.value, source_file_id: evidenceFile.value,
        source_page: evidencePage.value, source_quote: evidenceQuote.value,
        suggested_value: parseValue(evidenceValue.value) }),
    })
    evidenceQuote.value = ''
    manualEvidence.value = false
    await queryClient.invalidateQueries({ queryKey: ['field-evidence', id] })
  } catch (cause) { error.value = cause } finally { busy.value = false }
}
async function reviewEvidence(item: FieldEvidence, decision: 'confirm' | 'correct' | 'reject') {
  busy.value = true
  error.value = null
  try {
    await api.request(`/field-evidence/${item.id}/review`, {
      method: 'POST', body: JSON.stringify({ expected_revision: item.revision, decision,
        confirmed_value: decision === 'correct' ? parseValue(correctedValues.value[item.id] ?? '') : null }),
    })
    await queryClient.invalidateQueries({ queryKey: ['field-evidence', id] })
  } catch (cause) { error.value = cause } finally { busy.value = false }
}
async function openEvidenceSource(item: FieldEvidence) {
  try {
    const ticket = await api.request<{ url: string }>(`/field-evidence/${item.id}/source-download`, { method: 'POST' })
    window.location.assign(`${ticket.url}#page=${item.source_page}`)
  } catch (cause) { error.value = cause }
}
const users = useQuery({
  queryKey: ['users'],
  queryFn: () => api.request<Page<User>>('/users'),
})
const files = useQuery({
  queryKey: ['drive', 'case-picker'],
  queryFn: () => api.request<Page<DriveFile>>('/drive/files'),
})
const editing = ref(false)
const editTitle = ref('')
const payload = ref<Record<string, unknown>>({})
const fileIds = ref<string[]>([])
const errors = ref<Record<string, string>>({})
const error = ref<unknown>(null)
const busy = ref(false)
const dirty = computed(
  () =>
    editing.value &&
    (editTitle.value !== detail.data.value?.title ||
      JSON.stringify(payload.value) !==
        JSON.stringify(detail.data.value?.payload) ||
      JSON.stringify(fileIds.value) !==
        JSON.stringify(detail.data.value?.file_ids ?? [])),
)
const canEdit = computed(
  () =>
    ['draft', 'needs_revision'].includes(detail.data.value?.status ?? '') &&
    detail.data.value?.owner_id === session.user?.id,
)
// The approval inbox also lists tasks this user decides for someone who delegated to them.
const inbox = useQuery({
  queryKey: ['approvals', 'case', id],
  queryFn: () => api.request<Page<ApprovalTask>>('/approval-tasks'),
})
const myTask = computed(() =>
  inbox.data.value?.items.find(
    (task) =>
      task.case_id === id &&
      ['pending', 'waiting', 'open'].includes(task.status || task.state || 'pending'),
  ),
)
const canWithdraw = computed(
  () =>
    detail.data.value?.owner_id === session.user?.id &&
    ['pending_workflow_start', 'processing'].includes(detail.data.value?.status ?? '') &&
    !detail.data.value?.approval_tasks.some(
      (task) => task.decision && (task.state || task.status) !== 'cancelled',
    ),
)
const isOwner = computed(() => detail.data.value?.owner_id === session.user?.id)
const canDelete = computed(
  () => isOwner.value && detail.data.value?.status === 'draft' && !detail.data.value?.submission_no,
)
const canCancel = computed(
  () =>
    isOwner.value &&
    ['draft', 'needs_revision'].includes(detail.data.value?.status ?? '') &&
    !!detail.data.value?.submission_no,
)
const canArchive = computed(
  () =>
    (session.can('cases.read.department') || session.can('cases.read.organization')) &&
    ['approved', 'rejected', 'cancelled'].includes(detail.data.value?.status ?? ''),
)
type Closing = 'delete' | 'cancel' | 'archive' | 'unarchive'
const closing = ref<Closing | null>(null)
const CLOSING: Record<Closing, { title: string; text: string; button: string; done: string }> = {
  delete: {
    title: 'Xóa bản nháp',
    text: 'Bản nháp chưa từng trình nên chưa ai xem. Sau khi xóa, hồ sơ không còn trong danh sách và tìm kiếm; nhật ký hoạt động vẫn ghi lại việc xóa.',
    button: 'Xóa bản nháp',
    done: 'Đã xóa bản nháp',
  },
  cancel: {
    title: 'Hủy hồ sơ',
    text: 'Hồ sơ đã từng trình nên không xóa được. Hủy sẽ đóng hồ sơ, không trình lại được nữa; lịch sử duyệt vẫn được giữ và vẫn tìm thấy trong mục “Đã hủy”.',
    button: 'Hủy hồ sơ',
    done: 'Đã hủy hồ sơ',
  },
  archive: {
    title: 'Lưu trữ hồ sơ',
    text: 'Hồ sơ rời khỏi danh sách đang làm và chuyển sang mục “Lưu trữ”, giữ nguyên kết quả. Có thể bỏ lưu trữ bất cứ lúc nào.',
    button: 'Lưu trữ',
    done: 'Đã lưu trữ hồ sơ',
  },
  unarchive: {
    title: 'Bỏ lưu trữ',
    text: 'Hồ sơ trở lại danh sách hồ sơ thường.',
    button: 'Bỏ lưu trữ',
    done: 'Đã đưa hồ sơ trở lại danh sách',
  },
}
const closingReason = ref('')
async function closeCase() {
  const value = detail.data.value
  if (!value || !closing.value) return
  busy.value = true
  error.value = null
  const action = closing.value
  try {
    if (action === 'delete') {
      await api.request(`/cases/${id}?expected_revision=${value.revision}`, { method: 'DELETE' })
    } else if (action === 'cancel') {
      await api.request(`/cases/${id}/cancel`, {
        method: 'POST',
        body: JSON.stringify({ expected_revision: value.revision, reason: closingReason.value }),
      })
    } else {
      await api.request(`/cases/${id}/archive`, {
        method: 'POST',
        body: JSON.stringify({ expected_revision: value.revision, archived: action === 'archive' }),
      })
    }
    toast.success(CLOSING[action].done)
    closing.value = null
    await queryClient.invalidateQueries({ queryKey: ['cases'] })
    if (action === 'delete') await router.push('/cases')
    else await refresh()
  } catch (cause) {
    error.value = cause
  } finally {
    busy.value = false
  }
}
function askClosing(action: Closing) {
  closing.value = action
  closingReason.value = ''
  error.value = null
}
const ai = useAi()
const drafting = ref(false)
/** Let AI draft the approval note or return reason; the person edits it before confirming. */
async function draftReason() {
  if (!confirmation.value || !['approve', 'reject', 'return'].includes(confirmation.value)) return
  drafting.value = true
  try {
    const result = await api.request<{ text: string }>(`/ai/cases/${id}/decision-draft`, {
      method: 'POST',
      body: JSON.stringify({ decision: confirmation.value, notes: reason.value }),
    })
    reason.value = result.text
  } catch (cause) {
    toast.error(cause)
  } finally {
    drafting.value = false
  }
}
const confirmedEvidence = computed(() =>
  (fieldEvidence.data.value?.items ?? []).filter((item) => item.review_state === 'confirmed' && item.confirmed_value),
)
/** Put the values the author confirmed against the source documents into the form. */
function fillConfirmed() {
  startEdit()
  for (const item of confirmedEvidence.value) payload.value[item.field_key] = item.confirmed_value!.value
  toast.success(`Đã điền ${confirmedEvidence.value.length} giá trị vào biểu mẫu. Kiểm tra rồi bấm “Lưu bản nháp”.`)
}
const showTask = ref(false)
async function taskCreated(task: Task) {
  showTask.value = false
  await router.push(`/tasks/${task.id}`)
}
async function discuss() {
  try {
    const conversation = await api.request<Conversation>('/conversations', {
      method: 'POST',
      body: JSON.stringify({ kind: 'case', ref_id: id }),
    })
    await router.push(`/chat?c=${conversation.id}`)
  } catch (cause) {
    error.value = cause
  }
}
const confirmation = ref<'submit' | 'approve' | 'reject' | 'return' | 'withdraw' | null>(
  null,
)
const reason = ref('')
const intent = ref(newIntent())
const recipients = useQuery({
  queryKey: ['recipients', id],
  queryFn: () => api.request<Page<User>>(`/cases/${id}/eligible-recipients`),
  enabled: computed(() => confirmation.value === 'submit'),
})
const selectedSubmission = ref('')
const submission = computed(() => {
  const items = detail.data.value?.submissions ?? []
  return (
    items.find((item) => item.id === selectedSubmission.value) ?? items.at(-1)
  )
})
watch(
  () => detail.data.value?.submissions,
  (items) => {
    if (items?.length && !selectedSubmission.value)
      selectedSubmission.value = items.at(-1)!.id
  },
)
function userName(userId?: string) {
  return (
    users.data.value?.items.find((user) => user.id === userId)?.display_name ||
    (userId ? userId.slice(0, 8) : '—')
  )
}
function startEdit() {
  if (!detail.data.value) return
  editTitle.value = detail.data.value.title
  payload.value = JSON.parse(JSON.stringify(detail.data.value.payload))
  fileIds.value = [...(detail.data.value.file_ids ?? [])]
  errors.value = {}
  error.value = null
  editing.value = true
  tab.value = 'info'
}
function stopEdit() {
  if (confirmDiscard()) editing.value = false
}
async function refresh() {
  await queryClient.invalidateQueries({ queryKey: ['case', id] })
  await queryClient.invalidateQueries({ queryKey: ['case-explanation', id] })
  await queryClient.invalidateQueries({ queryKey: ['cases'] })
  await queryClient.invalidateQueries({ queryKey: ['approvals'] })
  await queryClient.invalidateQueries({ queryKey: ['notifications'] })
  await inbox.refetch()
}
async function save() {
  if (!detail.data.value) return
  errors.value = validatePayload(detail.data.value.form.fields, payload.value)
  if (Object.keys(errors.value).length) return
  busy.value = true
  error.value = null
  try {
    await api.request(`/cases/${id}`, {
      method: 'PATCH',
      headers: { 'Idempotency-Key': newIntent() },
      body: JSON.stringify({
        expected_revision: detail.data.value.revision,
        title: editTitle.value,
        payload: payload.value,
        file_ids: fileIds.value,
      } satisfies components['schemas']['CasePatch']),
    })
    editing.value = false
    await refresh()
    toast.success('Đã lưu bản nháp')
  } catch (cause) {
    error.value = cause
  } finally {
    busy.value = false
  }
}
function ask(action: typeof confirmation.value) {
  confirmation.value = action
  reason.value = ''
  error.value = null
  intent.value = newIntent()
}
const DONE = {
  submit: 'Đã chuyển hồ sơ đi duyệt',
  approve: 'Đã phê duyệt hồ sơ',
  reject: 'Đã từ chối hồ sơ',
  return: 'Đã trả hồ sơ cho người tạo',
  withdraw: 'Đã thu hồi hồ sơ về bản nháp',
}
async function confirm() {
  if (!detail.data.value) return
  busy.value = true
  error.value = null
  try {
    if (confirmation.value === 'withdraw')
      await api.request(`/cases/${id}/withdraw`, {
        method: 'POST',
        body: JSON.stringify({ expected_revision: detail.data.value.revision, reason: reason.value }),
      })
    else if (confirmation.value === 'submit')
      await api.request(`/cases/${id}/submit`, {
        method: 'POST',
        headers: { 'Idempotency-Key': intent.value },
        body: JSON.stringify({ expected_revision: detail.data.value.revision }),
      })
    else if (myTask.value && confirmation.value)
      await api.request(`/approval-tasks/${myTask.value.id}/decisions`, {
        method: 'POST',
        headers: { 'Idempotency-Key': intent.value },
        body: JSON.stringify({
          expected_revision: myTask.value.revision,
          decision: confirmation.value,
          reason: reason.value,
        } satisfies components['schemas']['DecisionInput']),
      })
    toast.success(DONE[confirmation.value ?? 'submit'])
    confirmation.value = null
    await refresh()
  } catch (cause) {
    error.value = cause
  } finally {
    busy.value = false
  }
}
async function download(file: DriveFile) {
  await downloadAttachment(file.id)
}
async function attachmentUrl(fileId: string, submissionId?: string) {
  const suffix = submissionId
    ? `?submission_id=${encodeURIComponent(submissionId)}`
    : ''
  const result = await api.request<{ url: string }>(
    `/cases/${id}/files/${fileId}/download${suffix}`,
    { method: 'POST' },
  )
  return result.url
}
async function downloadAttachment(fileId: string, submissionId?: string) {
  try {
    window.location.assign(await attachmentUrl(fileId, submissionId))
  } catch (cause) {
    error.value = cause
  }
}
// Submitted files open at the exact version that was submitted.
const preview = ref<{ fileId: string; name: string; submissionId?: string } | null>(null)
function eventLabel(event: HistoryEvent) {
  const actions: Record<string, string> = {
    'case.created': 'Đã tạo hồ sơ',
    'case.updated': 'Đã cập nhật bản nháp',
    'case.submitted': 'Đã trình duyệt',
    'case.withdrawn': 'Người tạo đã thu hồi hồ sơ',
    'case.approved': 'Hồ sơ được phê duyệt',
    'case.returned': 'Hồ sơ được trả lại',
    'case.rejected': 'Hồ sơ bị từ chối',
    'approval.decided': 'Đã ghi nhận quyết định',
    'case.workflow_started': 'Đã bắt đầu quy trình xử lý',
  }
  return actions[event.action] || event.action
}
function taskState(task: ApprovalTask) {
  return task.state || task.status || 'pending'
}
const { confirmDiscard } = useUnsavedGuard(dirty)
function parseValue(text: string): unknown {
  const value = text.trim()
  if (!value) return null
  try {
    return JSON.parse(value)
  } catch {
    return value
  }
}
function plainValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '(trống)'
  if (typeof value === 'boolean') return value ? 'Có' : 'Không'
  if (typeof value === 'number') return value.toLocaleString('vi-VN')
  if (Array.isArray(value)) return value.map(plainValue).join(', ')
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}
function fieldLabel(key: string) {
  const name = key.replace(/^payload\./, '')
  return detail.data.value?.form.fields.find((field) => field.key === name)?.label ?? name
}
type CaseTab = 'info' | 'files' | 'history' | 'route'
const tab = ref<CaseTab>('info')
const tabs = computed(() => {
  const data = detail.data.value
  const items: { key: CaseTab; label: string; icon: typeof Info; count?: number }[] = [
    { key: 'info', label: 'Thông tin', icon: Info },
    { key: 'files', label: 'Tài liệu', icon: Paperclip, count: data?.files?.length },
    { key: 'history', label: 'Lịch sử & bản đã trình', icon: History, count: data?.submissions.length },
  ]
  if (data?.submissions.length) items.push({ key: 'route', label: 'Vì sao đi đường này', icon: GitBranch })
  return items
})
function moveTab(step: number) {
  const keys = tabs.value.map((item) => item.key)
  const next = keys[(keys.indexOf(tab.value) + step + keys.length) % keys.length]
  tab.value = next
  document.getElementById(`case-tab-${next}`)?.focus()
}
</script>
<template>
  <div class="breadcrumb">
    <RouterLink to="/cases"
      ><ArrowLeft
        :size="14"
        style="vertical-align: middle; margin-right: 5px"
      />Hồ sơ</RouterLink
    ><span>/</span
    ><span>{{ detail.data.value?.code || 'Chi tiết hồ sơ' }}</span>
  </div>
  <StatePanel
    v-if="detail.isPending.value || detail.error.value"
    :loading="detail.isPending.value"
    :error="detail.error.value"
    @retry="detail.refetch()"
  />
  <template v-if="detail.data.value">
    <header class="page-head">
      <div>
        <span class="eyebrow">Mã hồ sơ {{ detail.data.value.code }}</span>
        <h1>{{ detail.data.value.title }}</h1>
        <div class="case-subline">
          <StatusBadge :status="detail.data.value.status" /><span v-if="detail.data.value.archived_at" class="tag"
            ><Archive :size="13" /> Lưu trữ</span
          ><span class="muted"
            >{{ detail.data.value.form.name }} · tạo bởi {{ userName(detail.data.value.owner_id) }}</span
          >
        </div>
      </div>
      <div v-if="!editing" class="page-actions">
        <button class="button secondary" @click="discuss">
          <MessagesSquare :size="16" />Trao đổi</button
        ><button
          v-if="session.can('tasks.create')"
          class="button secondary"
          @click="showTask = true"
        >
          <ListPlus :size="16" />Tạo việc</button
        ><button v-if="canWithdraw" class="button secondary" @click="ask('withdraw')">
          <Undo2 :size="16" />Thu hồi</button
        ><button v-if="canDelete" class="button secondary" @click="askClosing('delete')">
          <Trash2 :size="16" />Xóa bản nháp</button
        ><button v-if="canCancel" class="button secondary" @click="askClosing('cancel')">
          <Ban :size="16" />Hủy hồ sơ</button
        ><button
          v-if="canArchive"
          class="button secondary"
          @click="askClosing(detail.data.value.archived_at ? 'unarchive' : 'archive')"
        >
          <component :is="detail.data.value.archived_at ? ArchiveRestore : Archive" :size="16" />{{
            detail.data.value.archived_at ? 'Bỏ lưu trữ' : 'Lưu trữ'
          }}
        </button>
      </div>
    </header>
    <div
      v-if="error && !confirmation"
      class="notice error error-inline"
      role="alert"
    >
      <div>
        {{ errorText(error)
        }}<code v-if="error instanceof ApiError && error.traceId">Mã theo dõi: {{
          error.traceId
        }}</code
        ><button
          v-if="error instanceof ApiError && error.status === 409"
          class="button secondary small"
          style="margin-top: 10px"
          @click="
            () => {
              editing = false
              refresh()
            }
          "
        >
          Tải lại bản mới
        </button>
      </div>
    </div>
    <div
      v-if="detail.data.value.status === 'pending_workflow_start'"
      class="notice warning error-inline"
    >
      <History :size="18" /><span
        >Hồ sơ đã được tiếp nhận và đang chờ chuyển đến người duyệt. Hệ thống tự
        thử lại nếu chưa kết nối được; bạn không cần gửi thêm lần nữa.</span
      >
    </div>
    <section class="card case-progress">
      <div class="processing-rail" aria-label="Tiến trình xử lý">
        <div class="rail-step done">
          <span class="rail-circle"><Check :size="14" /></span>
          <div class="rail-content">
            <strong>Tạo hồ sơ</strong
            ><small>{{ userName(detail.data.value.owner_id) }}</small
            ><small>{{ formatDate(detail.data.value.created_at) }}</small>
          </div>
        </div>
        <div
          v-for="task in detail.data.value.approval_tasks"
          :key="task.id"
          class="rail-step"
          :class="{
            done: !!task.decision,
            current: ['pending', 'waiting'].includes(taskState(task)),
          }"
        >
          <span class="rail-circle"
            ><Check
              v-if="task.decision === 'approve'"
              :size="14"
            /><RotateCcw
              v-else-if="task.decision === 'return'"
              :size="12"
            /><XCircle
              v-else-if="task.decision === 'reject'"
              :size="12"
            /><span v-else>•</span></span
          >
          <div class="rail-content">
            <strong>{{
              task.label || task.step_label || 'Phê duyệt'
            }}</strong
            ><small>{{
              task.assignee_name || userName(task.assignee_id)
            }}</small
            ><small>{{
              task.decided_at
                ? formatDate(task.decided_at)
                : 'Chờ quyết định'
            }}</small>
          </div>
        </div>
        <div
          class="rail-step"
          :class="{ done: detail.data.value.status === 'approved' }"
        >
          <span class="rail-circle"><CheckCheck :size="13" /></span>
          <div class="rail-content">
            <strong>Hoàn tất</strong
            ><small>{{
              detail.data.value.status === 'approved'
                ? 'Đã phê duyệt'
                : 'Sau khi đủ quyết định'
            }}</small>
          </div>
        </div>
      </div>
    </section>
    <div class="tabs case-tabs" role="tablist" aria-label="Nội dung hồ sơ">
      <button
        v-for="item in tabs"
        :id="`case-tab-${item.key}`"
        :key="item.key"
        class="tab"
        :class="{ active: tab === item.key }"
        role="tab"
        :aria-selected="tab === item.key"
        :aria-controls="`case-panel-${item.key}`"
        :tabindex="tab === item.key ? 0 : -1"
        @click="tab = item.key"
        @keydown.right.prevent="moveTab(1)"
        @keydown.left.prevent="moveTab(-1)"
      >
        <component :is="item.icon" :size="16" />{{ item.label
        }}<span v-if="item.count" class="tab-count">{{ item.count }}</span>
      </button>
    </div>
    <div class="split">
      <div
        :id="`case-panel-${tab}`"
        class="stack"
        role="tabpanel"
        :aria-labelledby="`case-tab-${tab}`"
      >
        <CaseAiPanel
          v-if="tab === 'info' && !editing"
          :case-id="id"
          :can-edit="canEdit"
          :files="(detail.data.value.files ?? []).map((file) => ({ id: file.id, name: file.name }))"
        />
        <section v-if="tab === 'info'" class="card">
          <header class="card-header">
            <h2>Thông tin hồ sơ</h2>
            <span v-if="editing" class="tag">Đang chỉnh sửa bản nháp</span>
          </header>
          <div class="card-body">
            <div v-if="editing" class="field" style="margin-bottom: 22px">
              <label for="edit-case-title">Tên hồ sơ</label
              ><input
                id="edit-case-title"
                v-model="editTitle"
                required
                maxlength="255"
              />
            </div>
            <SchemaForm
              v-if="editing"
              v-model="payload"
              :fields="detail.data.value.form.fields"
              :errors="errors"
              :disabled="busy"
            /><SchemaForm
              v-else
              :model-value="detail.data.value.payload"
              :fields="detail.data.value.form.fields"
              readonly
            />
          </div>
        </section>
        <template v-if="tab === 'files'">
          <section class="card">
            <header class="card-header">
              <h2>Tài liệu đính kèm</h2>
              <Paperclip :size="18" class="muted" />
            </header>
            <div v-if="editing" class="card-body">
              <div class="case-document-list">
                <label
                  v-for="file in files.data.value?.items"
                  :key="file.id"
                  class="case-selection"
                  ><input
                    v-model="fileIds"
                    type="checkbox"
                    :value="file.id"
                  /><span>{{ file.name }}</span></label
                >
              </div>
              <p v-if="!files.data.value?.items.length" class="muted">
                Chưa có tệp. Tải tài liệu lên kho trước khi đính kèm.
              </p>
            </div>
            <template v-else
              ><div
                v-for="file in detail.data.value.files || []"
                :key="file.id"
                class="list-row"
              >
                <span class="file-icon"><FileText :size="19" /></span>
                <div class="grow">
                  <strong>{{ file.name }}</strong
                  ><small>Bản mới nhất trong kho · được chốt lại khi trình</small>
                </div>
                <button
                  v-if="previewKind(file.name)"
                  class="icon-button"
                  :aria-label="`Xem ${file.name}`"
                  title="Xem"
                  @click="preview = { fileId: file.id, name: file.name }"
                >
                  <Eye :size="17" />
                </button>
                <button
                  class="icon-button"
                  :aria-label="`Tải ${file.name}`"
                  title="Tải về"
                  @click="download(file)"
                >
                  <Download :size="17" />
                </button>
              </div>
              <StatePanel
                v-if="!detail.data.value.files?.length"
                empty
                compact
                title="Chưa đính kèm tài liệu"
                description="Gắn tài liệu từ kho khi chỉnh sửa bản nháp. Khi trình, bản đang có sẽ được chốt lại."
            /></template>
          </section>
          <section class="card">
            <header class="card-header"><div><span class="eyebrow">KIỂM TRA SỐ LIỆU</span><h2>Đối chiếu với tài liệu gốc</h2></div
              ><button v-if="canEdit && confirmedEvidence.length && !editing" class="button secondary small" @click="fillConfirmed">
                Điền {{ confirmedEvidence.length }} giá trị đã xác nhận vào biểu mẫu
              </button></header>
            <div class="card-body">
              <p class="muted">
                Mỗi giá trị trong biểu mẫu có thể kèm căn cứ: lấy từ trang nào, câu nào của tài liệu đính kèm, để người duyệt
                đối chiếu. Đề xuất do AI đọc tài liệu hiện ở đây để bạn xác nhận; việc xác nhận không tự sửa biểu mẫu.
              </p>
              <button
                v-if="canEdit && !manualEvidence"
                type="button"
                class="button ghost small"
                style="justify-self: start; margin-bottom: 10px"
                @click="manualEvidence = true"
              >
                <Plus :size="15" />Thêm căn cứ thủ công
              </button>
              <div v-if="canEdit && manualEvidence" class="form-grid">
                <div class="field"><label for="evidence-field">Mục trong biểu mẫu</label><select id="evidence-field" v-model="evidenceField"><option value="">Chọn mục</option><option v-for="field in detail.data.value.form.fields" :key="field.key" :value="field.key">{{ field.label }}</option></select></div>
                <div class="field"><label for="evidence-file">Tài liệu gốc</label><select id="evidence-file" v-model="evidenceFile"><option value="">Chọn tài liệu</option><option v-for="file in detail.data.value.files" :key="file.id" :value="file.id">{{ file.name }}</option></select></div>
                <div class="field"><label for="evidence-page">Trang</label><input id="evidence-page" v-model.number="evidencePage" type="number" min="1" /></div>
                <div class="field"><label for="evidence-value">Giá trị trong tài liệu</label><input id="evidence-value" v-model="evidenceValue" placeholder="Ví dụ: 12500000" /></div>
                <div class="field full-width"><label for="evidence-quote">Câu trích từ tài liệu</label><textarea id="evidence-quote" v-model="evidenceQuote" rows="2" /></div>
                <button class="button secondary" :disabled="busy || !evidenceField || !evidenceFile || !evidenceQuote" @click="addEvidence">Lưu đối chiếu</button>
              </div>
              <StatePanel :loading="fieldEvidence.isPending.value" :error="fieldEvidence.error.value"
                :empty="fieldEvidence.data.value?.items.length === 0" compact title="Chưa có đối chiếu nào" @retry="fieldEvidence.refetch()" />
              <div v-for="item in fieldEvidence.data.value?.items" :key="item.id" class="list-row">
                <div class="grow"><strong>{{ fieldLabel(item.field_key) }} · {{ item.review_state === 'confirmed' ? 'Đã xác nhận' : item.review_state === 'rejected' ? 'Đã bác bỏ' : 'Cần kiểm tra' }}</strong>
                  <small>{{ item.source_kind === 'ai' ? 'Gợi ý tự động' : 'Nhập tay' }}: {{ plainValue(item.suggested_value.value) }} · trang {{ item.source_page }}</small>
                  <small>Trích: “{{ item.source_quote }}”</small>
                  <small v-if="item.confirmed_value">Giá trị xác nhận: {{ plainValue(item.confirmed_value.value) }} · {{ userName(item.reviewed_by_id || '') }}</small>
                  <div v-if="canEdit && item.review_state === 'needs_review'" class="inline-actions">
                    <button class="button secondary small" :disabled="busy" @click="reviewEvidence(item, 'confirm')">Xác nhận</button>
                    <input v-model="correctedValues[item.id]" :aria-label="`Giá trị đúng cho ${fieldLabel(item.field_key)}`" placeholder="Giá trị đúng" />
                    <button class="button secondary small" :disabled="busy || !correctedValues[item.id]" @click="reviewEvidence(item, 'correct')">Sửa và xác nhận</button>
                    <button class="button ghost small" :disabled="busy" @click="reviewEvidence(item, 'reject')">Bác bỏ</button>
                  </div>
                </div>
                <button class="button ghost small" @click="openEvidenceSource(item)">Mở trang gốc</button>
              </div>
            </div>
          </section>
        </template>
        <template v-if="tab === 'history'">
          <section v-if="detail.data.value.submissions.length" class="card">
            <header class="card-header">
              <div>
                <span class="eyebrow">CĂN CỨ ĐỂ DUYỆT</span>
                <h2>Bản đã trình</h2>
              </div>
              <select
                v-model="selectedSubmission"
                aria-label="Chọn lần trình"
                style="width: auto; min-height: 34px; font-size: 13px"
              >
                <option
                  v-for="item in detail.data.value.submissions"
                  :key="item.id"
                  :value="item.id"
                >
                  Lần trình {{ item.number }}
                </option>
              </select>
            </header>
            <div v-if="submission" class="card-body">
              <div class="notice" style="margin-bottom: 20px">
                <ShieldCheck :size="18" /><span
                  >Đây là nội dung đúng như lúc trình ngày
                  {{ formatDate(submission.submitted_at || submission.created_at, true) }}.
                  Sửa hồ sơ về sau không làm thay đổi bản này.</span
                >
              </div>
              <SchemaForm
                :model-value="submission.payload_snapshot || {}"
                :fields="detail.data.value.form.fields"
                readonly
              />
              <div
                v-for="file in submission.files_snapshot"
                :key="file.version_id || file.id"
                class="list-row"
                style="padding-left: 0; padding-right: 0"
              >
                <FileText :size="18" />
                <div class="grow">
                  <p>{{ file.name || 'Tài liệu đã chốt' }}</p>
                  <small>Phiên bản đã chốt khi trình<template v-if="file.checksum"> · mã kiểm tra {{ String(file.checksum).slice(0, 10) }}</template></small>
                </div>
                <button
                  v-if="file.file_id && previewKind(file.name || '')"
                  class="icon-button"
                  aria-label="Xem đúng phiên bản đã trình"
                  title="Xem đúng phiên bản đã trình"
                  @click="preview = { fileId: file.file_id, name: file.name || 'Tài liệu', submissionId: submission.id }"
                >
                  <Eye :size="17" />
                </button>
                <button
                  v-if="file.file_id"
                  class="icon-button"
                  aria-label="Tải đúng phiên bản đã trình"
                  title="Tải đúng phiên bản đã trình"
                  @click="downloadAttachment(file.file_id, submission.id)"
                >
                  <Download :size="17" />
                </button>
              </div>
            </div>
          </section>
          <section class="card">
            <header class="card-header">
              <h2>Lịch sử xử lý</h2>
              <History :size="17" class="muted" />
            </header>
            <div class="card-body">
              <ul class="timeline">
                <li
                  v-for="(event, index) in detail.data.value.history"
                  :key="event.id || index"
                >
                  <p>{{ eventLabel(event) }}</p>
                  <small
                    >{{ userName(event.actor_id) }} ·
                    {{ formatDate(event.created_at, true) }}</small
                  >
                  <p
                    v-if="typeof event.detail === 'string'"
                    class="muted"
                    style="font-size: 13px; margin-top: 5px"
                  >
                    {{ event.detail }}
                  </p>
                  <p
                    v-else-if="event.detail?.reason"
                    class="muted"
                    style="font-size: 13px; margin-top: 5px"
                  >
                    {{ event.detail.reason }}
                  </p>
                </li>
              </ul>
              <p v-if="!detail.data.value.history.length" class="muted">
                Chưa có hoạt động.
              </p>
            </div>
          </section>
        </template>
        <section v-if="tab === 'route'" class="card">
          <header class="card-header"><h2>Vì sao hồ sơ được chuyển đến những người này?</h2></header>
          <div class="card-body">
            <p class="muted" style="margin-bottom: 14px">
              Quy trình chọn người duyệt dựa trên thông tin trong hồ sơ. Dưới đây là từng bước và lý do.
            </p>
            <StatePanel :loading="explanation.isPending.value" :error="explanation.error.value"
              :empty="!submission || !explanation.data.value?.submissions.length" compact title="Hồ sơ chưa được trình"
              description="Sau khi trình, phần này giải thích vì sao hồ sơ đi qua từng bước."
              @retry="explanation.refetch()" />
            <template v-for="item in explanation.data.value?.submissions" :key="item.submission_id">
              <div v-if="item.submission_id === submission?.id">
                <p class="muted">Lần trình {{ item.number }}</p>
                <div v-for="(step, index) in item.routing_evidence" :key="index" class="list-row">
                  <span class="route-mark" :class="{ on: step.selected }"><Check v-if="step.selected" :size="14" /><span v-else>–</span></span>
                  <div><strong>{{ step.label }}</strong><small>
                    {{ step.selected ? `Chuyển đến ${step.recipient}` : 'Không áp dụng cho hồ sơ này' }}
                    <template v-if="step.condition"> · vì “{{ fieldLabel(step.condition.field) }}” {{ OPERATORS[step.condition.operator] ?? step.condition.operator }} {{ plainValue(step.condition.value) }}
                      (hồ sơ ghi: {{ plainValue(step.evaluated_value) }})</template>
                  </small></div>
                </div>
                <div v-for="trace in item.decision_traces" :key="trace.node_id" class="list-row">
                  <span class="route-mark" :class="{ on: trace.result }"><Check v-if="trace.result" :size="14" /><span v-else>–</span></span>
                  <div><strong>Điều kiện “{{ fieldLabel(trace.expression.path) }}” {{ OPERATORS[trace.expression.operator] ?? trace.expression.operator }} {{ plainValue(trace.expression.value) }}: {{ trace.result ? 'đúng' : 'không đúng' }}</strong>
                    <small>Hồ sơ ghi: {{ plainValue(trace.evaluated_inputs[trace.expression.path]) }}</small></div>
                </div>
              </div>
            </template>
          </div>
        </section>
      </div>
      <aside class="stack" style="align-content: start">
        <section class="card">
          <header class="card-header"><h3>Tóm tắt</h3></header>
          <dl class="detail-meta card-body">
            <div>
              <dt>Người tạo</dt>
              <dd>{{ userName(detail.data.value.owner_id) }}</dd>
            </div>
            <div>
              <dt>Ngày tạo</dt>
              <dd>{{ formatDate(detail.data.value.created_at, true) }}</dd>
            </div>
            <div>
              <dt>Cập nhật gần nhất</dt>
              <dd>{{ formatDate(detail.data.value.updated_at, true) }}</dd>
            </div>
            <div>
              <dt>Số lần trình</dt>
              <dd>{{ detail.data.value.submissions.length }}</dd>
            </div>
          </dl>
        </section>
        <div class="notice">
          <ShieldCheck :size="19" /><span
            >Quyết định có hiệu lực khi hệ thống ghi nhận. Trang tự cập nhật theo
            tiến trình xử lý.</span
          >
        </div>
      </aside>
    </div>
    <div v-if="editing" class="sticky-actions" role="region" aria-label="Lưu bản nháp">
      <span><Pencil :size="16" />{{ dirty ? 'Có thay đổi chưa lưu' : 'Đang chỉnh sửa bản nháp' }}</span>
      <button class="button secondary" :disabled="busy" @click="stopEdit">Hủy</button
      ><button class="button" :disabled="busy" @click="save">
        <Save :size="17" />{{ busy ? 'Đang lưu…' : 'Lưu bản nháp' }}
      </button>
    </div>
    <div v-else-if="myTask" class="sticky-actions" role="region" aria-label="Quyết định của bạn">
      <span
        ><ClipboardCheck :size="17" /><span
          >Bạn cần quyết định:
          <strong>{{ myTask.label || myTask.step_label || 'Phê duyệt hồ sơ' }}</strong
          ><template v-if="myTask.on_behalf_of"> (duyệt thay {{ myTask.on_behalf_of }})</template></span
        ></span
      >
      <button class="button secondary" @click="ask('return')">
        <RotateCcw :size="15" />Trả lại</button
      ><button class="button danger" @click="ask('reject')">Từ chối</button
      ><button class="button" @click="ask('approve')">
        <Check :size="16" />Phê duyệt
      </button>
    </div>
    <div v-else-if="canEdit" class="sticky-actions" role="region" aria-label="Bản nháp">
      <span
        ><Pencil :size="16" />{{
          detail.data.value.status === 'needs_revision'
            ? 'Hồ sơ được trả lại để sửa. Chỉnh rồi trình lại.'
            : 'Bản nháp — kiểm tra lại trước khi trình.'
        }}</span
      >
      <button class="button secondary" @click="startEdit">
        <Pencil :size="16" />Chỉnh sửa</button
      ><button class="button" @click="ask('submit')">
        <Send :size="16" />Chuyển duyệt
      </button>
    </div>
  </template>
  <ModalDialog
    v-if="confirmation"
    :title="
      confirmation === 'submit'
        ? 'Chuyển hồ sơ để phê duyệt'
        : confirmation === 'approve'
          ? 'Phê duyệt hồ sơ'
          : confirmation === 'return'
            ? 'Trả hồ sơ để chỉnh sửa'
            : confirmation === 'withdraw'
              ? 'Thu hồi hồ sơ đã trình'
              : 'Từ chối hồ sơ'
    "
    @close="
      () => {
        if (!busy) confirmation = null
      }
    "
    ><div v-if="error" class="notice error error-inline" role="alert">
      {{ errorText(error) }}
    </div>
    <form @submit.prevent="confirm">
      <div class="stack">
        <p>
          <strong>{{ detail.data.value?.title }}</strong>
        </p>
        <template v-if="confirmation === 'submit'"
          ><div class="notice">
            <ShieldCheck :size="20" /><span
              >Thông tin biểu mẫu và phiên bản tài liệu được chụp lại làm căn cứ
              duyệt. Tất cả phiên chỉnh sửa tài liệu phải hoàn tất lưu trước khi
              trình.</span
            >
          </div>
          <div>
            <span class="section-label">Người nhận hợp lệ theo quy trình</span
            ><StatePanel
              :loading="recipients.isPending.value"
              :error="recipients.error.value"
              @retry="recipients.refetch()"
            />
            <div
              v-for="user in recipients.data.value?.items"
              :key="user.id"
              class="list-row"
              style="padding: 10px 0"
            >
              <span class="avatar">{{
                user.display_name.split(' ').slice(-1)[0]?.slice(0, 1)
              }}</span
              ><span>{{ user.display_name }}</span>
            </div>
          </div></template
        ><template v-else
          ><p class="muted">
            {{
              confirmation === 'approve'
                ? 'Xác nhận đã kiểm tra nội dung và các tài liệu của lần trình hiện tại.'
                : confirmation === 'return'
                  ? 'Người tạo sẽ được chỉnh sửa và trình lại. Lịch sử và bản đã trình vẫn được giữ nguyên.'
                  : confirmation === 'withdraw'
                    ? 'Hồ sơ trở về bản nháp để bạn chỉnh sửa và trình lại. Chỉ thu hồi được khi chưa ai ra quyết định; bản đã trình vẫn được giữ trong lịch sử.'
                    : 'Quyết định từ chối được lưu lại cùng hồ sơ và lý do.'
            }}
          </p>
          <div class="field">
            <label for="decision-reason"
              >{{
                confirmation === 'approve' || confirmation === 'withdraw'
                  ? 'Ghi chú (không bắt buộc)'
                  : 'Lý do'
              }}<span
                v-if="confirmation !== 'approve' && confirmation !== 'withdraw'"
                class="required"
              >
                *</span
              ></label
            ><textarea
              id="decision-reason"
              v-model="reason"
              rows="4"
              :required="confirmation !== 'approve' && confirmation !== 'withdraw'"
              :disabled="busy"
              placeholder="Ghi rõ nội dung cần lưu ý…"
            /><button
              v-if="ai.on('decision_draft') && myTask && ['approve', 'reject', 'return'].includes(confirmation ?? '')"
              type="button"
              class="button secondary small ai-action"
              style="justify-self: start; margin-top: 6px"
              :disabled="drafting || busy"
              @click="draftReason"
            >
              <Sparkles :size="14" />{{ drafting ? 'AI đang soạn…' : reason ? 'Soạn lại bằng AI (dựa trên ghi chú)' : 'Gợi ý bằng AI' }}
            </button></div
        ></template>
      </div>
      <div class="form-actions">
        <button
          type="button"
          class="button secondary"
          :disabled="busy"
          @click="confirmation = null"
        >
          Hủy</button
        ><button
          class="button"
          :class="{ danger: confirmation === 'reject' }"
          :disabled="
            busy || (confirmation === 'submit' && !!recipients.error.value)
          "
        >
          {{
            busy
              ? 'Đang ghi nhận…'
              : confirmation === 'submit'
                ? 'Xác nhận chuyển duyệt'
                : confirmation === 'approve'
                  ? 'Xác nhận phê duyệt'
                  : confirmation === 'return'
                    ? 'Trả lại hồ sơ'
                    : confirmation === 'withdraw'
                      ? 'Thu hồi hồ sơ'
                      : 'Xác nhận từ chối'
          }}
        </button>
      </div>
    </form></ModalDialog
  >
  <ModalDialog
    v-if="closing"
    :title="CLOSING[closing].title"
    @close="
      () => {
        if (!busy) closing = null
      }
    "
    ><div v-if="error" class="notice error error-inline" role="alert">{{ errorText(error) }}</div>
    <form @submit.prevent="closeCase">
      <div class="stack">
        <p><strong>{{ detail.data.value?.title }}</strong></p>
        <p class="muted">{{ CLOSING[closing].text }}</p>
        <div v-if="closing === 'cancel'" class="field">
          <label for="closing-reason">Lý do (không bắt buộc)</label
          ><textarea id="closing-reason" v-model="closingReason" rows="3" maxlength="2000" :disabled="busy" />
        </div>
      </div>
      <div class="form-actions">
        <button type="button" class="button secondary" :disabled="busy" @click="closing = null">Quay lại</button
        ><button class="button" :class="{ danger: closing === 'delete' || closing === 'cancel' }" :disabled="busy">
          {{ busy ? 'Đang ghi nhận…' : CLOSING[closing].button }}
        </button>
      </div>
    </form></ModalDialog
  >
  <FilePreview
    v-if="preview"
    :key="`${preview.fileId}:${preview.submissionId ?? ''}`"
    :name="preview.name"
    :source="() => attachmentUrl(preview!.fileId, preview!.submissionId)"
    :download="() => downloadAttachment(preview!.fileId, preview!.submissionId)"
    @close="preview = null"
  />
  <TaskCreateDialog
    v-if="showTask && detail.data.value"
    heading="Tạo việc từ hồ sơ"
    :case-id="id"
    :default-title="detail.data.value.title"
    @close="showTask = false"
    @created="taskCreated"
  />
</template>
