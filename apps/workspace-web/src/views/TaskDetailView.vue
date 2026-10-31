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
  FileText,
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
const canTick = computed(
  () =>
    !!task.value &&
    !['completed', 'cancelled'].includes(task.value.status) &&
    (canManage.value || task.value.assignee_id === session.user?.id),
)
const priorityLabel = { low: 'Thấp', normal: 'Bình thường', high: 'Cao', urgent: 'Khẩn' }
const eventLabels: Record<string, string> = {
  created: 'Tạo công việc',
  assigned: 'Giao / phân công',
  accept: 'Tiếp nhận',
  start: 'Bắt đầu thực hiện',
  submit: 'Nộp kết quả',
  complete: 'Nghiệm thu hoàn tất',
  return: 'Trả lại',
  block: 'Báo vướng mắc',
  unblock: 'Tiếp tục xử lý',
  cancel: 'Hủy việc',
  due_changed: 'Đổi hạn',
  automation_attached: 'Gắn luồng tự động',
  automation_detached: 'Gỡ luồng tự động',
  updated: 'Cập nhật',
}
async function run(work: () => Promise<unknown>) {
  busy.value = true
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
  }
}
function ask(action: TaskAction) {
  if (action !== 'assign' && !actionMeta[action].needsReason && action !== 'submit') {
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
async function transition(action: TaskAction) {
  if (!task.value) return
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
  )
  if (ok) {
    pending.value = null
    if (action !== 'assign') toast.success(DONE[action])
  }
}
async function assign() {
  if (!task.value || !assignTarget.value) return
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
  await run(() =>
    api.request(`/tasks/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ expected_revision: task.value!.revision, checklist }),
    }),
  )
}
async function changeDue() {
  if (!task.value || !dueEdit.value) return
  const ok = await run(() =>
    api.request(`/tasks/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({
        expected_revision: task.value!.revision,
        due_at: dueEdit.value!.value ? new Date(dueEdit.value!.value).toISOString() : null,
        due_reason: dueEdit.value!.reason,
      }),
    }),
  )
  if (ok) {
    dueEdit.value = null
    toast.success('Đã đổi hạn')
  }
}
async function addComment() {
  if (!comment.value.trim()) return
  const ok = await run(() =>
    api.request(`/tasks/${id}/comments`, {
      method: 'POST',
      body: JSON.stringify({ body: comment.value }),
    }),
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
  })
}
function localInput(value: string | null) {
  if (!value) return ''
  const date = new Date(value)
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
}
</script>
<template>
  <div class="breadcrumb">
    <RouterLink to="/tasks"
      ><ArrowLeft :size="14" style="vertical-align: middle; margin-right: 5px" />Công
      việc</RouterLink
    ><span>/</span
    ><template v-if="task?.parent"
      ><RouterLink :to="`/tasks/${task.parent.id}`">{{ task.parent.title }}</RouterLink
      ><span>/</span></template
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
        <span class="eyebrow">CÔNG VIỆC · r{{ task.revision }}</span>
        <h1>{{ task.title }}</h1>
        <div class="inline-actions" style="margin-top: 12px">
          <StatusBadge kind="task" :status="task.status" /><span
            class="priority"
            :class="`priority-${task.priority}`"
            >{{ priorityLabel[task.priority] }}</span
          ><span v-if="task.overdue" class="overdue-text"
            ><AlarmClock :size="14" /> Quá hạn</span
          >
        </div>
      </div>
      <div class="page-actions">
        <button class="button secondary" :disabled="busy" @click="discuss">
          <MessagesSquare :size="16" />Trao đổi
        </button>
        <button v-if="canManage" class="button secondary" @click="ask('assign')">
          <UserRoundPlus :size="16" />Giao lại
        </button>
        <button
          v-for="action in transitions"
          :key="action"
          class="button"
          :class="actionMeta[action].tone"
          :disabled="busy"
          @click="ask(action)"
        >
          <component :is="actionMeta[action].icon" :size="16" />{{
            actionMeta[action].label
          }}
        </button>
      </div>
    </header>
    <div v-if="error && !pending" class="notice error error-inline" role="alert">
      <div>
        {{ errorText(error)
        }}<button
          v-if="error instanceof ApiError && error.status === 409"
          class="button secondary small"
          style="margin-left: 10px"
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
        <section class="card">
          <header class="card-header">
            <h2>Việc con</h2>
            <button
              v-if="!['completed', 'cancelled'].includes(task.status)"
              class="button ghost small"
              @click="showSubtask = true"
            >
              <Plus :size="15" />Thêm việc con
            </button>
          </header>
          <p v-if="!task.subtasks.length" class="step-empty" style="padding: 18px 23px">
            Chưa có việc con. Việc cha chỉ nghiệm thu khi mọi việc con đã xong hoặc hủy.
          </p>
          <TaskBreakdown
            v-if="ai.on('task_breakdown') && !['completed', 'cancelled'].includes(task.status)"
            :task-id="task.id"
            :case-id="task.case_id"
            @created="detail.refetch()"
          />
          <RouterLink
            v-for="child in task.subtasks"
            :key="child.id"
            :to="`/tasks/${child.id}`"
            class="list-row"
            style="color: inherit; text-decoration: none"
          >
            <div class="grow">
              <p>{{ child.title }}</p>
              <small>{{ child.assignee_name || 'Chưa giao' }}</small>
            </div>
            <StatusBadge kind="task" :status="child.status" />
          </RouterLink>
        </section>
        <section class="card">
          <header class="card-header"><h2>Trao đổi trong công việc</h2></header>
          <div class="card-body stack">
            <p v-if="!task.comments.length" class="muted">Chưa có bình luận.</p>
            <div v-for="item in task.comments" :key="item.id" class="comment">
              <span class="avatar">{{ item.author_name.split(' ').slice(-1)[0]?.[0] }}</span>
              <div>
                <strong>{{ item.author_name }}</strong>
                <small class="muted"> · {{ formatDate(item.created_at, true) }}</small>
                <p class="prewrap">{{ item.body }}</p>
              </div>
            </div>
            <form class="comment-form" @submit.prevent="addComment">
              <textarea
                v-model="comment"
                rows="2"
                placeholder="Viết bình luận…"
                aria-label="Bình luận"
              /><button class="button" :disabled="busy || !comment.trim()">Gửi</button>
            </form>
          </div>
        </section>
      </div>
      <aside class="stack" style="align-content: start">
        <section class="card">
          <header class="card-header"><h3>Thông tin</h3></header>
          <dl class="card-body detail-meta">
            <div><dt>Người giao</dt><dd>{{ task.creator_name }}</dd></div>
            <div>
              <dt>Người chịu trách nhiệm</dt>
              <dd>
                {{ task.assignee_name || 'Chờ trưởng đơn vị phân công' }}
              </dd>
            </div>
            <div v-if="task.department_name">
              <dt>Đơn vị nhận</dt><dd>{{ task.department_name }}</dd>
            </div>
            <div>
              <dt>Hạn hoàn thành</dt>
              <dd :class="{ 'overdue-text': task.overdue }">
                {{ formatDate(task.due_at, true) }}
                <button
                  v-if="canManage"
                  class="button ghost small"
                  @click="dueEdit = { value: localInput(task.due_at), reason: '' }"
                >
                  <CalendarClock :size="14" />Đổi hạn
                </button>
              </dd>
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
            <div v-if="task.files.length">
              <dt>Tài liệu</dt>
              <dd>
                <span v-for="file in task.files" :key="file.id" class="file-chip"
                  ><FileText :size="14" />{{
                    file.restricted ? 'Tài liệu bạn chưa được cấp quyền' : file.name
                  }}</span
                >
              </dd>
            </div>
            <div><dt>Tạo lúc</dt><dd>{{ formatDate(task.created_at, true) }}</dd></div>
          </dl>
        </section>
        <TaskAutomations :task-id="task.id" :closed="['completed', 'cancelled'].includes(task.status)" />
        <section class="card">
          <header class="card-header"><h3>Hoạt động</h3></header>
          <div class="card-body">
            <ul class="timeline">
              <li v-for="event in task.events" :key="event.id">
                <p>{{ eventLabels[event.action] ?? event.action }}</p>
                <small
                  >{{ event.actor_name }} · {{ formatDate(event.created_at, true)
                  }}<template v-if="event.detail?.reason">
                    · “{{ event.detail.reason }}”</template
                  ></small
                >
              </li>
            </ul>
          </div>
        </section>
      </aside>
    </div>
    <ModalDialog
      v-if="pending"
      :title="pending === 'assign' ? 'Giao lại công việc' : actionMeta[pending].label"
      @close="pending = null"
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
          ><textarea id="task-result" v-model="result" rows="4" />
          <small v-if="task.checklist_done < task.checklist_total" class="field-error"
            >Còn {{ task.checklist_total - task.checklist_done }} mục checklist chưa xong.</small
          >
        </div>
        <div class="field">
          <label for="task-reason"
            >Lý do<span
              v-if="pending !== 'assign' && pending !== 'submit' && actionMeta[pending].needsReason"
              class="required"
            >
              *</span
            ></label
          ><textarea
            id="task-reason"
            v-model="reason"
            rows="3"
            :required="pending !== 'assign' && pending !== 'submit' && actionMeta[pending].needsReason"
          />
        </div>
        <div class="form-actions">
          <button type="button" class="button secondary" @click="pending = null">Hủy</button
          ><button class="button" :disabled="busy">Xác nhận</button>
        </div>
      </form>
    </ModalDialog>
    <ModalDialog v-if="dueEdit" title="Đổi hạn hoàn thành" @close="dueEdit = null">
      <div v-if="error" class="notice error error-inline" role="alert">
        {{ errorText(error) }}
      </div>
      <form class="stack" @submit.prevent="changeDue">
        <div class="field">
          <label for="due-new">Hạn mới</label
          ><input id="due-new" v-model="dueEdit.value" type="datetime-local" />
        </div>
        <div class="field">
          <label for="due-reason">Lý do đổi hạn<span class="required"> *</span></label
          ><textarea id="due-reason" v-model="dueEdit.reason" rows="3" required />
          <small>Hạn cũ, hạn mới và người thay đổi được lưu vào lịch sử.</small>
        </div>
        <div class="form-actions">
          <button type="button" class="button secondary" @click="dueEdit = null">Hủy</button
          ><button class="button" :disabled="busy">Lưu</button>
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
