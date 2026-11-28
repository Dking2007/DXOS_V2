<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import {
  AlarmClock,
  ArrowLeft,
  Ban,
  CalendarClock,
  Check,
  CheckCheck,
  CircleAlert,
  MessagesSquare,
  Play,
  Plus,
  RotateCcw,
  Send,
  UserRoundPlus,
} from 'lucide-vue-next'
import { api } from '../api'
import { toast } from '../ui/toast'
import { useSession } from '../stores/session'
import { ApiError, errorText, formatDate } from '@dx/web-shared/api.ts'
import type { Conversation, TaskAction, TaskDetail } from '@dx/web-shared/types.ts'
import StatePanel from '@dx/web-shared/components/StatePanel.vue'
import StatusBadge from '@dx/web-shared/components/StatusBadge.vue'
import ModalDialog from '@dx/web-shared/components/ModalDialog.vue'
import TaskCreateDialog from '../components/TaskCreateDialog.vue'
import TaskBreakdown from '../ai/TaskBreakdown.vue'
import { useAi } from '../ai/useAi'
import TaskAutomations from '../components/TaskAutomations.vue'
import PluginFrames from '../components/plugins/PluginFrames.vue'
import PluginActions from '../components/plugins/PluginActions.vue'
import TaskFiles from '../components/TaskFiles.vue'
import TaskActivity from '../components/TaskActivity.vue'
import { TASK_STAGES, dueText, nextStep, taskStage } from '../ui/taskGuide'
import { initialsOf } from '../ui/people'
import { confirmDiscard } from '../ui/unsaved'
import { reasonMissing } from '../components/workForms'
const route = useRoute()
const router = useRouter()
const queryClient = useQueryClient()
const session = useSession()
const id = String(route.params.id)
const detail = useQuery({
  queryKey: ['task', id],
  queryFn: () => api.request<TaskDetail>(`/tasks/${id}`),
})
const task = computed(() => detail.data.value)
const busy = ref(false)
/** Which button started the request in flight, so only that one says "Đang …". */
const running = ref<string>('')
const error = ref<unknown>(null)
const pending = ref<TaskAction | null>(null)
const reason = ref('')
const result = ref('')
const showSubtask = ref(false)
const ai = useAi()
const comment = ref('')
const dueEdit = ref<{ value: string; reason: string } | null>(null)
const assignTarget = ref('')
const assignable = useQuery({
  queryKey: ['tasks', 'assignable'],
  queryFn: () =>
    api.request<{
      users: { id: string; display_name: string }[]
      departments: { id: string; name: string }[]
    }>('/tasks/assignable-users'),
  enabled: computed(() => pending.value === 'assign'),
})
const actionMeta: Record<
  Exclude<TaskAction, 'assign'>,
  { label: string; icon: unknown; tone?: string; needsReason?: boolean }
> = {
  accept: { label: 'Tiếp nhận', icon: Check },
  start: { label: 'Bắt đầu làm', icon: Play, tone: 'secondary' },
  submit: { label: 'Nộp kết quả', icon: Send },
  complete: { label: 'Nghiệm thu', icon: CheckCheck },
  return: { label: 'Trả lại', icon: RotateCcw, tone: 'secondary', needsReason: true },
  block: { label: 'Báo vướng mắc', icon: CircleAlert, tone: 'secondary', needsReason: true },
  unblock: { label: 'Tiếp tục', icon: Play, tone: 'secondary' },
  cancel: { label: 'Hủy việc', icon: Ban, tone: 'danger', needsReason: true },
}
const transitions = computed(
  () =>
    (task.value?.actions ?? []).filter((action) => action !== 'assign') as Exclude<
      TaskAction,
      'assign'
    >[],
)
const canManage = computed(() => task.value?.actions.includes('assign') ?? false)
const closed = computed(() => ['completed', 'cancelled'].includes(task.value?.status ?? ''))
const canCreate = computed(() => session.can('tasks.create'))
// The step that moves the work forward comes first; talking about it and the rest follow.
const primaryActions = computed(() => transitions.value.filter((action) => !actionMeta[action].tone))
const otherActions = computed(() =>
  transitions.value.filter((action) => actionMeta[action].tone && actionMeta[action].tone !== 'danger'),
)
// Destructive actions sit last, away from the step people usually want.
const dangerActions = computed(() => transitions.value.filter((action) => actionMeta[action].tone === 'danger'))
const stage = computed(() => (task.value ? taskStage(task.value.status) : 0))
const due = computed(() => (task.value ? dueText(task.value.due_at, task.value.status) : ''))
const guide = computed(() => {
  const value = task.value
  if (!value) return null
  const last = [...value.events].reverse().find((event) => ['return', 'block', 'cancel'].includes(event.action))
  return nextStep({
    status: value.status,
    isAssignee: value.assignee_id === session.user?.id,
    canManage: canManage.value,
    hasAssignee: !!value.assignee_id,
    overdue: value.overdue,
    reason: typeof last?.detail?.reason === 'string' ? last.detail.reason : undefined,
    requiredFiles: (value as { required_file_count?: number }).required_file_count ?? 0,
    fileCount: value.files.length,
  })
})
const canTick = computed(
  () =>
    !!task.value &&
    !['completed', 'cancelled'].includes(task.value.status) &&
    (canManage.value || task.value.assignee_id === session.user?.id),
)
const priorityLabel = { low: 'Thấp', normal: 'Bình thường', high: 'Cao', urgent: 'Khẩn' }
async function run(work: () => Promise<unknown>, label = '') {
  if (busy.value) return false
  busy.value = true
  running.value = label
  error.value = null
  try {
    await work()
    await queryClient.invalidateQueries({ queryKey: ['task', id] })
    await queryClient.invalidateQueries({ queryKey: ['tasks'] })
    return true
  } catch (cause) {
    error.value = cause
    return false
  } finally {
    busy.value = false
    running.value = ''
  }
}
// Steps that only move the work along run at once; handing in, signing off, sending back,
// reporting a problem and cancelling are confirmed in a dialog first.
const IMMEDIATE: TaskAction[] = ['accept', 'start', 'unblock']
function ask(action: TaskAction) {
  if (IMMEDIATE.includes(action)) {
    void transition(action)
    return
  }
  pending.value = action
  reason.value = ''
  result.value = task.value?.result ?? ''
  assignTarget.value = ''
  error.value = null
}
const DONE: Record<Exclude<TaskAction, 'assign'>, string> = {
  accept: 'Đã tiếp nhận việc',
  start: 'Đã chuyển sang đang làm',
  submit: 'Đã nộp kết quả, chờ người giao nghiệm thu',
  complete: 'Đã nghiệm thu, việc hoàn tất',
  return: 'Đã trả lại để làm tiếp',
  block: 'Đã báo vướng mắc cho người giao',
  unblock: 'Việc được tiếp tục',
  cancel: 'Đã hủy việc',
}
const pendingDirty = computed(
  () =>
    !!reason.value.trim() ||
    !!assignTarget.value ||
    (pending.value === 'submit' && result.value !== (task.value?.result ?? '')),
)
async function closePending() {
  if (!busy.value && await confirmDiscard(pendingDirty.value)) pending.value = null
}
/** Why the dialog's confirm button cannot go through yet, checked before the server says so. */
const pendingBlocked = computed(() => {
  const value = task.value
  const action = pending.value
  if (!value || !action) return ''
  if (action === 'assign') return assignTarget.value ? '' : 'Chọn người hoặc đơn vị nhận.'
  if (reasonMissing(!!actionMeta[action].needsReason, reason.value)) return 'Nêu lý do trước khi xác nhận.'
  if (action === 'submit' && value.checklist_done < value.checklist_total)
    return 'Hoàn thành checklist trước khi nộp kết quả.'
  const required = (value as { required_file_count?: number }).required_file_count ?? 0
  if (action === 'submit' && value.files.length < required)
    return `Cần đính kèm ít nhất ${required} tệp kết quả trước khi nộp.`
  if (action === 'complete' && value.subtasks.some((child) => !['completed', 'cancelled'].includes(child.status)))
    return 'Còn việc con chưa hoàn tất hoặc hủy.'
  return ''
})
const CONFIRM_TEXT: Record<Exclude<TaskAction, 'assign'>, string> = {
  accept: 'Tiếp nhận',
  start: 'Bắt đầu',
  submit: 'Nộp kết quả',
  complete: 'Xác nhận nghiệm thu',
  return: 'Trả lại',
  block: 'Báo vướng mắc',
  unblock: 'Tiếp tục',
  cancel: 'Hủy việc',
}
async function transition(action: TaskAction) {
  if (!task.value) return
  if (pending.value && pendingBlocked.value) return
  const ok = await run(() =>
    api.request(`/tasks/${id}/transitions`, {
      method: 'POST',
      body: JSON.stringify({
        expected_revision: task.value!.revision,
        action,
        reason: reason.value,
        result: action === 'submit' ? result.value : null,
      }),
    }),
    action,
  )
  if (ok) {
    pending.value = null
    if (action !== 'assign') toast.success(DONE[action])
  }
}
async function assign() {
  if (!task.value || pendingBlocked.value) return
  const [kind, target] = assignTarget.value.split(':')
  const ok = await run(() =>
    api.request(`/tasks/${id}/assign`, {
      method: 'POST',
      body: JSON.stringify({
        expected_revision: task.value!.revision,
        assignee_id: kind === 'user' ? target : null,
        department_id: kind === 'dept' ? target : null,
        reason: reason.value,
      }),
    }),
    'assign',
  )
  if (ok) {
    pending.value = null
    toast.success('Đã phân công lại')
  }
}
async function toggle(index: number) {
  if (!task.value) return
  const checklist = task.value.checklist.map((item, i) =>
    i === index ? { ...item, done: !item.done } : item,
  )
  await run(
    () =>
      api.request(`/tasks/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ expected_revision: task.value!.revision, checklist }),
      }),
    'checklist',
  )
}
const dueBlocked = computed(() =>
  dueEdit.value && reasonMissing(true, dueEdit.value.reason) ? 'Nêu lý do đổi hạn.' : '',
)
async function closeDue() {
  if (!busy.value && await confirmDiscard(!!dueEdit.value?.reason.trim())) dueEdit.value = null
}
async function changeDue() {
  if (!task.value || !dueEdit.value || dueBlocked.value) return
  const ok = await run(() =>
    api.request(`/tasks/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({
        expected_revision: task.value!.revision,
        due_at: dueEdit.value!.value ? new Date(dueEdit.value!.value).toISOString() : null,
        due_reason: dueEdit.value!.reason,
      }),
    }),
    'due',
  )
  if (ok) {
    dueEdit.value = null
    toast.success('Đã đổi hạn')
  }
}
async function addComment() {
  if (!comment.value.trim()) return
  const ok = await run(
    () =>
      api.request(`/tasks/${id}/comments`, {
        method: 'POST',
        body: JSON.stringify({ body: comment.value }),
      }),
    'comment',
  )
  if (ok) comment.value = ''
}
async function discuss() {
  await run(async () => {
    const conversation = await api.request<Conversation>('/conversations', {
      method: 'POST',
      body: JSON.stringify({ kind: 'task', ref_id: id }),
    })
    await router.push(`/chat?c=${conversation.id}`)
  }, 'discuss')
}
function localInput(value: string | null) {
  if (!value) return ''
  const date = new Date(value)
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
}
</script>
<template>
  <div class="breadcrumb">
    <RouterLink to="/tasks" class="crumb-back"
      ><ArrowLeft :size="14" aria-hidden="true" />Công việc</RouterLink
    ><span aria-hidden="true">/</span
    ><template v-if="task?.parent"
      ><RouterLink :to="`/tasks/${task.parent.id}`" class="crumb-title" :title="task.parent.title">{{
        task.parent.title
      }}</RouterLink
      ><span aria-hidden="true">/</span></template
    ><span>Chi tiết</span>
  </div>
  <StatePanel
    v-if="detail.isPending.value || detail.error.value"
    :loading="detail.isPending.value"
    :error="detail.error.value"
    @retry="detail.refetch()"
  />
  <template v-if="task">
    <header class="page-head">
      <div>
        <h1 class="task-heading">{{ task.title }}</h1>
        <div class="inline-actions task-badges">
          <StatusBadge kind="task" :status="task.status" /><span
            class="priority"
            :class="`priority-${task.priority}`"
            >{{ priorityLabel[task.priority] }}</span
          ><span v-if="due" class="task-due" :class="task.overdue ? 'overdue-text' : 'muted'"
            ><AlarmClock :size="14" aria-hidden="true" />{{ due }}</span
          >
        </div>
      </div>
      <div class="page-actions">
        <PluginActions place="task.action" :context="{ task_id: task.id }" />
        <button
          v-for="action in primaryActions"
          :key="action"
          class="button"
          :disabled="busy"
          @click="ask(action)"
        >
          <component :is="actionMeta[action].icon" :size="16" />{{
            running === action && !pending ? 'Đang xử lý…' : actionMeta[action].label
          }}
        </button>
        <button
          v-for="action in otherActions"
          :key="action"
          class="button"
          :class="actionMeta[action].tone"
          :disabled="busy"
          @click="ask(action)"
        >
          <component :is="actionMeta[action].icon" :size="16" />{{
            running === action && !pending ? 'Đang xử lý…' : actionMeta[action].label
          }}
        </button>
        <button v-if="canManage" class="button secondary" :disabled="busy" @click="ask('assign')">
          <UserRoundPlus :size="16" />Giao lại
        </button>
        <button class="button secondary" :disabled="busy" @click="discuss">
          <MessagesSquare :size="16" />{{ running === 'discuss' ? 'Đang mở…' : 'Trao đổi' }}
        </button>
        <button
          v-for="action in dangerActions"
          :key="action"
          class="button danger"
          :disabled="busy"
          @click="ask(action)"
        >
          <component :is="actionMeta[action].icon" :size="16" />{{ actionMeta[action].label }}
        </button>
      </div>
    </header>
    <section class="task-summary card" aria-label="Tình trạng công việc">
      <ol v-if="stage >= 0" class="task-stages" aria-label="Các giai đoạn">
        <li
          v-for="(label, index) in TASK_STAGES"
          :key="label"
          :class="{ done: index < stage || stage === 4, current: index === stage && stage < 4 }"
          :aria-current="index === stage ? 'step' : undefined"
        >
          <span class="task-stage-dot" aria-hidden="true"
            ><Check v-if="index < stage || stage === 4" :size="12" /></span
          >{{ label }}
        </li>
      </ol>
      <p v-if="guide" class="task-next" :class="guide.tone">{{ guide.text }}</p>
      <dl class="task-facts">
        <div><dt>Người giao</dt><dd>{{ task.creator_name }}</dd></div>
        <div>
          <dt>Người thực hiện</dt>
          <dd>{{ task.assignee_name || task.department_name || 'Chờ phân công' }}</dd>
        </div>
        <div>
          <dt>Hạn hoàn thành</dt>
          <dd :class="{ 'overdue-text': task.overdue }">
            {{ task.due_at ? formatDate(task.due_at, true) : 'Không đặt hạn' }}
            <button
              v-if="canManage && !closed"
              class="button ghost small due-change"
              :disabled="busy"
              @click="dueEdit = { value: localInput(task.due_at), reason: '' }"
            >
              <CalendarClock :size="14" />Đổi hạn
            </button>
          </dd>
        </div>
        <div v-if="task.checklist_total">
          <dt>Checklist</dt>
          <dd>{{ task.checklist_done }}/{{ task.checklist_total }} mục</dd>
        </div>
      </dl>
    </section>
    <div v-if="error && !pending" class="notice error error-inline" role="alert">
      <div>
        {{ errorText(error)
        }}<button
          v-if="error instanceof ApiError && error.status === 409"
          class="button secondary small notice-action"
          @click="detail.refetch()"
        >
          Tải bản mới
        </button>
      </div>
    </div>
    <div class="split">
      <div class="stack">
        <section class="card">
          <header class="card-header"><h2>Nội dung</h2></header>
          <div class="card-body stack">
            <p v-if="task.description" class="prewrap">{{ task.description }}</p>
            <p v-else class="muted">Không có mô tả.</p>
            <div v-if="task.checklist.length">
              <span class="section-label"
                >Checklist · {{ task.checklist_done }}/{{ task.checklist_total }}</span
              >
              <div class="progress-track" aria-hidden="true">
                <span
                  :style="{
                    width: `${(task.checklist_done / task.checklist_total) * 100}%`,
                  }"
                />
              </div>
              <label
                v-for="(item, index) in task.checklist"
                :key="item.id ?? index"
                class="checkbox-label"
                :class="{ done: item.done }"
                ><input
                  type="checkbox"
                  :checked="item.done"
                  :disabled="!canTick || busy"
                  @change="toggle(index)"
                />{{ item.text }}</label
              >
            </div>
            <div v-if="task.result" class="notice success">
              <CheckCheck :size="18" /><span
                ><strong>Kết quả đã nộp:</strong> {{ task.result }}</span
              >
            </div>
          </div>
        </section>
        <TaskFiles
          :task-id="task.id"
          :files="task.files"
          :revision="task.revision"
          :closed="closed"
          :can-manage="canManage"
          :is-assignee="task.assignee_id === session.user?.id"
          @changed="detail.refetch()"
        />
        <section class="card">
          <header class="card-header">
            <h2>Việc con</h2>
            <button v-if="!closed && canCreate" class="button ghost small" @click="showSubtask = true">
              <Plus :size="15" />Thêm việc con
            </button>
          </header>
          <p v-if="!task.subtasks.length" class="step-empty card-pad">
            Chưa có việc con. Việc cha chỉ nghiệm thu khi mọi việc con đã xong hoặc hủy.
          </p>
          <TaskBreakdown
            v-if="ai.on('task_breakdown') && !closed && canCreate"
            :task-id="task.id"
            :case-id="task.case_id"
            @created="detail.refetch()"
          />
          <RouterLink
            v-for="child in task.subtasks"
            :key="child.id"
            :to="`/tasks/${child.id}`"
            class="list-row plain-link"
          >
            <div class="grow">
              <p class="ellipsis" :title="child.title">{{ child.title }}</p>
              <small>{{ child.assignee_name || 'Chưa giao' }}</small>
            </div>
            <StatusBadge kind="task" :status="child.status" />
          </RouterLink>
        </section>
        <section class="card">
          <header class="card-header"><h2>Bình luận</h2></header>
          <div class="card-body stack">
            <p v-if="!task.comments.length" class="muted">Chưa có bình luận.</p>
            <div v-for="item in task.comments" :key="item.id" class="comment">
              <span class="avatar" aria-hidden="true">{{ initialsOf(item.author_name) }}</span>
              <div class="comment-body">
                <div class="comment-meta">
                  <strong>{{ item.author_name }}</strong>
                  <small class="muted"
                    ><template v-if="item.via">qua plugin {{ item.via }} · </template
                    >{{ formatDate(item.created_at, true) }}</small
                  >
                </div>
                <p class="prewrap">{{ item.body }}</p>
              </div>
            </div>
            <form class="comment-form" @submit.prevent="addComment">
              <textarea
                v-model="comment"
                rows="2"
                maxlength="5000"
                placeholder="Viết bình luận… (Ctrl + Enter để gửi)"
                aria-label="Bình luận"
                @keydown.ctrl.enter.prevent="addComment"
                @keydown.meta.enter.prevent="addComment"
              /><button class="button" :disabled="busy || !comment.trim()">
                <Send :size="15" />{{ running === 'comment' ? 'Đang gửi…' : 'Gửi' }}
              </button>
            </form>
          </div>
        </section>
      </div>
      <aside class="stack task-aside">
        <section class="card">
          <header class="card-header"><h3>Chi tiết</h3></header>
          <dl class="card-body detail-meta">
            <div v-if="task.department_name">
              <dt>Đơn vị nhận</dt><dd>{{ task.department_name }}</dd>
            </div>
            <div v-if="task.watchers.length">
              <dt>Người theo dõi</dt>
              <dd>{{ task.watchers.map((w) => w.display_name).join(', ') }}</dd>
            </div>
            <div v-if="task.case">
              <dt>Hồ sơ liên quan</dt>
              <dd>
                <RouterLink :to="`/cases/${task.case.id}`"
                  >{{ task.case.code }} · {{ task.case.title }}</RouterLink
                >
              </dd>
            </div>
            <div v-if="task.source?.type && task.source.type !== 'manual'">
              <dt>Nguồn</dt>
              <dd>
                {{
                  { message: 'Tin nhắn', post: 'Bài viết', case: 'Hồ sơ', automation: 'Tự động hóa' }[
                    task.source.type
                  ] ?? task.source.type
                }}<span v-if="task.source.label" class="muted">: “{{ task.source.label }}”</span>
              </dd>
            </div>
            <div><dt>Tạo lúc</dt><dd>{{ formatDate(task.created_at, true) }}</dd></div>
          </dl>
        </section>
        <TaskAutomations :task-id="task.id" :closed="closed" />
        <PluginFrames place="task.side" :context="{ task_id: task.id }" />
        <TaskActivity :events="task.events" />
      </aside>
    </div>
    <ModalDialog
      v-if="pending"
      :title="pending === 'assign' ? 'Giao lại công việc' : actionMeta[pending].label"
      @close="closePending"
    >
      <div v-if="error" class="notice error error-inline" role="alert">
        {{ errorText(error) }}
      </div>
      <form class="stack" @submit.prevent="pending === 'assign' ? assign() : transition(pending)">
        <div v-if="pending === 'assign'" class="field">
          <label for="assign-target">Người / đơn vị nhận</label
          ><select id="assign-target" v-model="assignTarget" required>
            <option value="">Chọn người nhận</option>
            <optgroup label="Cá nhân">
              <option
                v-for="user in assignable.data.value?.users"
                :key="user.id"
                :value="`user:${user.id}`"
              >
                {{ user.display_name }}
              </option>
            </optgroup>
            <optgroup v-if="assignable.data.value?.departments.length" label="Đơn vị">
              <option
                v-for="unit in assignable.data.value?.departments"
                :key="unit.id"
                :value="`dept:${unit.id}`"
              >
                {{ unit.name }}
              </option>
            </optgroup>
          </select>
        </div>
        <div v-if="pending === 'submit'" class="field">
          <label for="task-result">Kết quả thực hiện</label
          ><textarea id="task-result" v-model="result" rows="4" maxlength="5000" :disabled="busy" />
          <small v-if="task.checklist_done < task.checklist_total" class="field-error"
            >Còn {{ task.checklist_total - task.checklist_done }} mục checklist chưa xong. Đánh dấu
            xong trước khi nộp.</small
          >
        </div>
        <p v-if="pending === 'complete'" class="muted">
          Nghiệm thu sẽ đóng công việc và báo cho người thực hiện. Sau khi hoàn tất không sửa được
          checklist, tài liệu hay hạn nữa.
        </p>
        <p v-else-if="pending === 'cancel'" class="muted">
          Hủy việc sẽ dừng mọi xử lý và báo cho người thực hiện. Lịch sử vẫn được giữ lại.
        </p>
        <div class="field">
          <label for="task-reason"
            >{{
              pending !== 'assign' && actionMeta[pending].needsReason ? 'Lý do' : 'Ghi chú (không bắt buộc)'
            }}<span v-if="pending !== 'assign' && actionMeta[pending].needsReason" class="required">
              *</span
            ></label
          ><textarea
            id="task-reason"
            v-model="reason"
            rows="3"
            maxlength="2000"
            :disabled="busy"
            :required="pending !== 'assign' && actionMeta[pending].needsReason"
          />
        </div>
        <div class="form-actions">
          <button type="button" class="button secondary" :disabled="busy" @click="closePending">Hủy</button
          ><button
            class="button"
            :class="{ danger: pending === 'cancel' }"
            :disabled="busy || !!pendingBlocked"
            :title="pendingBlocked"
          >
            {{ busy ? 'Đang ghi nhận…' : pending === 'assign' ? 'Giao lại' : CONFIRM_TEXT[pending] }}
          </button>
        </div>
      </form>
    </ModalDialog>
    <ModalDialog v-if="dueEdit" title="Đổi hạn hoàn thành" @close="closeDue">
      <div v-if="error" class="notice error error-inline" role="alert">
        {{ errorText(error) }}
      </div>
      <form class="stack" @submit.prevent="changeDue">
        <div class="field">
          <label for="due-new">Hạn mới</label
          ><input id="due-new" v-model="dueEdit.value" type="datetime-local" :disabled="busy" />
          <small>Để trống nếu việc không còn hạn.</small>
        </div>
        <div class="field">
          <label for="due-reason">Lý do đổi hạn<span class="required"> *</span></label
          ><textarea id="due-reason" v-model="dueEdit.reason" rows="3" maxlength="2000" required :disabled="busy" />
          <small>Hạn cũ, hạn mới và người thay đổi được lưu vào lịch sử.</small>
        </div>
        <div class="form-actions">
          <button type="button" class="button secondary" :disabled="busy" @click="closeDue">Hủy</button
          ><button class="button" :disabled="busy || !!dueBlocked" :title="dueBlocked">
            {{ busy ? 'Đang lưu…' : 'Lưu hạn mới' }}
          </button>
        </div>
      </form>
    </ModalDialog>
    <TaskCreateDialog
      v-if="showSubtask"
      heading="Thêm việc con"
      :parent-id="task.id"
      :case-id="task.case_id ?? undefined"
      @close="showSubtask = false"
      @created="
        () => {
          showSubtask = false
          detail.refetch()
        }
      "
    />
  </template>
</template>
<style scoped>
.crumb-back {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.crumb-title {
  max-width: 320px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.task-heading {
  overflow-wrap: anywhere;
}
.task-badges {
  margin-top: 12px;
}
.task-due {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.due-change {
  margin-left: 8px;
}
.notice-action {
  margin-left: 12px;
}
.card-pad {
  padding: 18px 23px;
}
.plain-link {
  color: inherit;
  text-decoration: none;
}
.ellipsis {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.task-aside {
  align-content: start;
}
.comment-body {
  min-width: 0;
  flex: 1;
}
.comment-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 4px 8px;
}
.comment-form textarea {
  flex: 1;
  min-width: 0;
}
@media (max-width: 640px) {
  .comment-form {
    flex-direction: column;
    align-items: stretch;
  }
  .crumb-title {
    max-width: 180px;
  }
}
</style>
