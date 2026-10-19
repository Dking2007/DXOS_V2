<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { onBeforeRouteLeave, RouterLink, useRoute } from 'vue-router'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import {
  ArrowLeft,
  Check,
  CheckCheck,
  ClipboardCheck,
  Download,
  FileText,
  History,
  Paperclip,
  Pencil,
  RotateCcw,
  Save,
  Send,
  ShieldCheck,
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
const route = useRoute()
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
const myTask = computed(() =>
  detail.data.value?.approval_tasks.find(
    (task) =>
      task.assignee_id === session.user?.id &&
      ['pending', 'waiting', 'open'].includes(
        task.status || task.state || 'pending',
      ),
  ),
)
const confirmation = ref<'submit' | 'approve' | 'reject' | 'return' | null>(
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
}
function stopEdit() {
  if (!dirty.value || window.confirm('Bỏ các thay đổi chưa lưu?'))
    editing.value = false
}
async function refresh() {
  await queryClient.invalidateQueries({ queryKey: ['case', id] })
  await queryClient.invalidateQueries({ queryKey: ['cases'] })
  await queryClient.invalidateQueries({ queryKey: ['approvals'] })
  await queryClient.invalidateQueries({ queryKey: ['notifications'] })
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
async function confirm() {
  if (!detail.data.value) return
  busy.value = true
  error.value = null
  try {
    if (confirmation.value === 'submit')
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
async function downloadAttachment(fileId: string, submissionId?: string) {
  try {
    const suffix = submissionId
      ? `?submission_id=${encodeURIComponent(submissionId)}`
      : ''
    const result = await api.request<{ url: string }>(
      `/cases/${id}/files/${fileId}/download${suffix}`,
      { method: 'POST' },
    )
    window.location.assign(result.url)
  } catch (cause) {
    error.value = cause
  }
}
function eventLabel(event: HistoryEvent) {
  const actions: Record<string, string> = {
    'case.created': 'Đã tạo hồ sơ',
    'case.updated': 'Đã cập nhật bản nháp',
    'case.submitted': 'Đã trình duyệt',
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
const beforeUnload = (event: BeforeUnloadEvent) => {
  if (dirty.value) event.preventDefault()
}
window.addEventListener('beforeunload', beforeUnload)
onBeforeUnmount(() => window.removeEventListener('beforeunload', beforeUnload))
onBeforeRouteLeave(
  () =>
    !dirty.value ||
    window.confirm('Hồ sơ có thay đổi chưa lưu. Bạn muốn rời trang?'),
)
</script>
<template>
  <div class="breadcrumb">
    <RouterLink to="/cases"
      ><ArrowLeft
        :size="14"
        style="vertical-align: middle; margin-right: 5px"
      />Hồ sơ</RouterLink
    ><span>/</span
    ><span class="mono">{{ detail.data.value?.code || 'Chi tiết hồ sơ' }}</span>
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
        <span class="eyebrow mono"
          >{{ detail.data.value.code }} · r{{
            detail.data.value.revision
          }}</span
        >
        <h1>{{ detail.data.value.title }}</h1>
        <div
          style="
            margin-top: 12px;
            display: flex;
            gap: 12px;
            align-items: center;
          "
        >
          <StatusBadge :status="detail.data.value.status" /><span
            class="muted"
            style="font-size: 13px"
            >{{ detail.data.value.form.name }}</span
          >
        </div>
      </div>
      <div class="page-actions">
        <template v-if="editing"
          ><button class="button secondary" :disabled="busy" @click="stopEdit">
            Hủy chỉnh sửa</button
          ><button class="button" :disabled="busy" @click="save">
            <Save :size="17" />{{ busy ? 'Đang lưu…' : 'Lưu bản nháp' }}
          </button></template
        ><template v-else-if="canEdit"
          ><button class="button secondary" @click="startEdit">
            <Pencil :size="16" />Chỉnh sửa</button
          ><button class="button" @click="ask('submit')">
            <Send :size="16" />Chuyển duyệt
          </button></template
        >
      </div>
    </header>
    <div
      v-if="error && !confirmation"
      class="notice error error-inline"
      role="alert"
    >
      <div>
        {{ errorText(error)
        }}<code v-if="error instanceof ApiError && error.traceId">{{
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
        >Hồ sơ đã được tiếp nhận và đang chờ khởi tạo quy trình. Hệ thống sẽ tự
        thử lại nếu Core chưa sẵn sàng; không cần gửi thêm lần nữa.</span
      >
    </div>
    <div
      v-if="myTask && !editing"
      class="notice error-inline"
      style="
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
      "
    >
      <div style="display: flex; gap: 10px; align-items: center">
        <ClipboardCheck :size="18" /><span
          >Bạn được phân công:
          <strong>{{
            myTask.label || myTask.step_label || 'Phê duyệt hồ sơ'
          }}</strong></span
        >
      </div>
      <div class="inline-actions">
        <button class="button secondary small" @click="ask('return')">
          <RotateCcw :size="14" />Trả lại</button
        ><button class="button danger small" @click="ask('reject')">
          Từ chối</button
        ><button class="button small" @click="ask('approve')">
          <Check :size="15" />Phê duyệt
        </button>
      </div>
    </div>
    <div class="split">
      <div class="stack">
        <section class="card">
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
          <header class="card-header">
            <h2>Thông tin hồ sơ</h2>
            <span class="tag">{{
              editing
                ? 'Đang chỉnh sửa nháp'
                : `Biểu mẫu v${detail.data.value.form.schema_version ?? 1}`
            }}</span>
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
                ><small class="mono">{{
                  file.current_version_id || file.id
                }}</small>
              </div>
              <button
                class="icon-button"
                aria-label="Tải tài liệu đính kèm"
                @click="download(file)"
              >
                <Download :size="17" />
              </button>
            </div>
            <StatePanel
              v-if="!detail.data.value.files?.length"
              empty
              title="Chưa đính kèm tài liệu"
              description="Tài liệu được gắn từ kho và chốt phiên bản khi trình hồ sơ."
          /></template>
        </section>
        <section v-if="detail.data.value.submissions.length" class="card">
          <header class="card-header">
            <div>
              <span class="eyebrow">NGUỒN CĂN CỨ PHÊ DUYỆT</span>
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
                >Snapshot bất biến · payload r{{
                  submission.payload_revision ?? '—'
                }}
                ·
                {{
                  formatDate(
                    submission.submitted_at || submission.created_at,
                    true,
                  )
                }}</span
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
                <p>{{ file.name || 'Tài liệu đã ghim' }}</p>
                <small class="mono">{{ file.version_id }}</small
                ><small class="mono">SHA256 {{ file.checksum }}</small>
              </div>
              <button
                v-if="file.file_id"
                class="icon-button"
                aria-label="Tải đúng phiên bản đã trình"
                @click="downloadAttachment(file.file_id, submission.id)"
              >
                <Download :size="17" />
              </button>
            </div>
          </div>
        </section>
      </div>
      <aside class="stack" style="align-content: start">
        <section class="card">
          <header class="card-header"><h3>Thông tin quản lý</h3></header>
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
              <dt>Revision hiện tại</dt>
              <dd class="mono">{{ detail.data.value.revision }}</dd>
            </div>
            <div>
              <dt>Số lần trình</dt>
              <dd>{{ detail.data.value.submissions.length }}</dd>
            </div>
          </dl>
        </section>
        <section class="card">
          <header class="card-header">
            <h3>Lịch sử xử lý</h3>
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
                  style="font-size: 12px; margin-top: 5px"
                >
                  {{ event.detail }}
                </p>
                <p
                  v-else-if="event.detail?.reason"
                  class="muted"
                  style="font-size: 12px; margin-top: 5px"
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
        <div class="notice">
          <ShieldCheck :size="19" /><span
            >Quyết định có hiệu lực sau khi được ghi nhận trên máy chủ. Dữ liệu
            trên trang tự cập nhật theo tiến trình.</span
          >
        </div>
      </aside>
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
                  : 'Quyết định từ chối được lưu lại cùng hồ sơ và lý do.'
            }}
          </p>
          <div class="field">
            <label for="decision-reason"
              >{{
                confirmation === 'approve'
                  ? 'Ý kiến phê duyệt (không bắt buộc)'
                  : 'Lý do'
              }}<span v-if="confirmation !== 'approve'" class="required">
                *</span
              ></label
            ><textarea
              id="decision-reason"
              v-model="reason"
              rows="4"
              :required="confirmation !== 'approve'"
              :disabled="busy"
              placeholder="Ghi rõ nội dung cần lưu ý…"
            /></div
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
                    : 'Xác nhận từ chối'
          }}
        </button>
      </div>
    </form></ModalDialog
  >
</template>
