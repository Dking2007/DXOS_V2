<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { Plus, Sparkles, Trash2 } from 'lucide-vue-next'
import { api } from '../api'
import { ApiError, errorText } from '@dx/web-shared/api.ts'
import type { Task } from '@dx/web-shared/types.ts'
import ModalDialog from '@dx/web-shared/components/ModalDialog.vue'
import { toast } from '../ui/toast'
import { confirmDiscard } from '../ui/unsaved'
import { useAi } from '../ai/useAi'
const props = defineProps<{
  parentId?: string
  caseId?: string
  source?: { type: string; id?: string; label?: string }
  defaultTitle?: string
  heading?: string
  /** A sentence to turn into the form with AI as soon as the dialog opens (e.g. from a chat summary). */
  sentence?: string
}>()
const emit = defineEmits<{ close: []; created: [task: Task] }>()
interface Assignable {
  users: { id: string; display_name: string; department_id: string | null }[]
  departments: { id: string; name: string }[]
  scope: 'self' | 'department' | 'organization'
}
const options = useQuery({
  queryKey: ['tasks', 'assignable'],
  queryFn: () => api.request<Assignable>('/tasks/assignable-users'),
})
const title = ref(props.defaultTitle ?? '')
const description = ref('')
const target = ref('')
const priority = ref<Task['priority']>('normal')
const dueAt = ref('')
const checklist = ref<string[]>([])
const watcherIds = ref<string[]>([])
const busy = ref(false)
const error = ref<unknown>(null)
const ai = useAi()
const sentence = ref(props.sentence ?? '')
const parsing = ref(false)
const parseNote = ref('')
function localInput(iso: string) {
  const date = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}
/** Fill the form from one sentence; nothing is assigned until the person presses the button. */
async function parse() {
  if (sentence.value.trim().length < 3) return
  parsing.value = true
  parseNote.value = ''
  try {
    const draft = await api.request<{
      title: string
      description: string
      assignee_id: string | null
      department_id: string | null
      due_at: string | null
      priority: Task['priority']
      checklist: string[]
    }>('/ai/tasks/parse', { method: 'POST', body: JSON.stringify({ text: sentence.value }) })
    title.value = draft.title
    description.value = draft.description || description.value
    priority.value = draft.priority
    if (draft.due_at) dueAt.value = localInput(draft.due_at)
    if (draft.checklist.length) checklist.value = draft.checklist
    const users = options.data.value?.users ?? []
    const units = options.data.value?.departments ?? []
    if (draft.assignee_id && users.some((u) => u.id === draft.assignee_id)) target.value = `user:${draft.assignee_id}`
    else if (draft.department_id && units.some((d) => d.id === draft.department_id)) target.value = `dept:${draft.department_id}`
    else if (draft.assignee_id || draft.department_id)
      parseNote.value = 'Người được nhắc tới nằm ngoài phạm vi bạn được giao việc; hãy chọn người nhận.'
    else parseNote.value = 'AI chưa xác định được người nhận; hãy chọn trong danh sách.'
  } catch (cause) {
    toast.error(cause)
  } finally {
    parsing.value = false
  }
}
onMounted(() => {
  if (props.sentence && ai.on('task_parse')) parse()
})
const scopeHint = computed(
  () =>
    ({
      self: 'Bạn có thể tạo việc cho chính mình.',
      department: 'Bạn giao việc trong phòng của mình.',
      organization: 'Bạn giao việc cho mọi người và đơn vị trong tổ chức.',
    })[options.data.value?.scope ?? 'self'],
)
const dirty = computed(
  () =>
    title.value !== (props.defaultTitle ?? '') ||
    !!description.value.trim() ||
    !!target.value ||
    !!dueAt.value ||
    priority.value !== 'normal' ||
    checklist.value.some((item) => item.trim()) ||
    watcherIds.value.length > 0,
)
function close() {
  if (!busy.value && confirmDiscard(dirty.value)) emit('close')
}
async function submit() {
  busy.value = true
  error.value = null
  const [kind, id] = target.value.split(':')
  try {
    const task = await api.request<Task>('/tasks', {
      method: 'POST',
      body: JSON.stringify({
        title: title.value,
        description: description.value,
        assignee_id: kind === 'user' ? id : null,
        department_id: kind === 'dept' ? id : null,
        priority: priority.value,
        due_at: dueAt.value ? new Date(dueAt.value).toISOString() : null,
        checklist: checklist.value
          .filter((item) => item.trim())
          .map((text) => ({ text, done: false })),
        watcher_ids: watcherIds.value,
        parent_id: props.parentId ?? null,
        case_id: props.caseId ?? null,
        source: props.source ?? null,
      }),
    })
    toast.success(target.value ? `Đã giao việc “${task.title}”` : `Đã tạo việc “${task.title}”`)
    emit('created', task)
  } catch (cause) {
    error.value = cause
  } finally {
    busy.value = false
  }
}
</script>
<template>
  <ModalDialog :title="heading || 'Giao việc mới'" wide @close="close">
    <div v-if="error" class="notice error error-inline" role="alert">
      <div>
        {{ errorText(error)
        }}<code v-if="error instanceof ApiError && error.traceId">{{
          error.traceId
        }}</code>
      </div>
    </div>
    <div v-if="source?.label" class="notice error-inline">
      <span
        >Tạo từ {{ source.type === 'message' ? 'tin nhắn' : 'nguồn' }}:
        <em>“{{ source.label }}”</em></span
      >
    </div>
    <form @submit.prevent="submit">
      <div v-if="ai.on('task_parse')" class="ai-card" style="margin-bottom: 16px">
        <label class="ai-title" for="task-sentence"><Sparkles :size="16" />Giao việc bằng một câu</label>
        <div class="inline-actions" style="margin-top: 8px">
          <input
            id="task-sentence"
            v-model="sentence"
            class="grow"
            maxlength="2000"
            placeholder="Ví dụ: Giao Châu tổng hợp báo cáo quý IV, hạn thứ Sáu, ưu tiên cao"
            @keydown.enter.prevent="parse"
          />
          <button type="button" class="button secondary small ai-action" :disabled="parsing || sentence.trim().length < 3" @click="parse">
            {{ parsing ? 'Đang điền…' : 'Điền bằng AI' }}
          </button>
        </div>
        <p v-if="parseNote" class="ai-note">{{ parseNote }}</p>
        <p v-else class="ai-note">AI điền sẵn các ô bên dưới; bạn xem lại rồi mới bấm Giao việc.</p>
      </div>
      <div class="form-grid">
        <div class="field full-width">
          <label for="task-title">Tên công việc<span class="required"> *</span></label
          ><input
            id="task-title"
            v-model="title"
            required
            maxlength="250"
            autofocus
            placeholder="Ví dụ: Tổng hợp báo cáo tuần"
          />
        </div>
        <div class="field full-width">
          <label for="task-description">Nội dung, yêu cầu</label
          ><textarea id="task-description" v-model="description" rows="3" />
        </div>
        <div class="field">
          <label for="task-target">Người / đơn vị nhận</label
          ><select id="task-target" v-model="target">
            <option value="">Lưu nháp, chưa giao</option>
            <optgroup v-if="options.data.value?.users.length" label="Cá nhân">
              <option
                v-for="user in options.data.value?.users"
                :key="user.id"
                :value="`user:${user.id}`"
              >
                {{ user.display_name }}
              </option>
            </optgroup>
            <optgroup
              v-if="options.data.value?.departments.length"
              label="Đơn vị (trưởng đơn vị phân công tiếp)"
            >
              <option
                v-for="unit in options.data.value?.departments"
                :key="unit.id"
                :value="`dept:${unit.id}`"
              >
                {{ unit.name }}
              </option>
            </optgroup></select
          ><small>{{ scopeHint }}</small>
        </div>
        <div class="field">
          <label for="task-due">Hạn hoàn thành</label
          ><input id="task-due" v-model="dueAt" type="datetime-local" />
        </div>
        <div class="field">
          <label for="task-priority">Mức ưu tiên</label
          ><select id="task-priority" v-model="priority">
            <option value="low">Thấp</option>
            <option value="normal">Bình thường</option>
            <option value="high">Cao</option>
            <option value="urgent">Khẩn</option>
          </select>
        </div>
        <div class="field">
          <label for="task-watchers">Người theo dõi</label
          ><select id="task-watchers" v-model="watcherIds" multiple size="3">
            <option
              v-for="user in options.data.value?.users"
              :key="user.id"
              :value="user.id"
            >
              {{ user.display_name }}
            </option>
          </select>
        </div>
        <div class="field full-width">
          <label>Checklist cần hoàn thành trước khi nộp</label>
          <div v-for="(_, index) in checklist" :key="index" class="checklist-edit">
            <input
              v-model="checklist[index]"
              :aria-label="`Mục ${index + 1}`"
              maxlength="300"
            /><button
              type="button"
              class="icon-button"
              aria-label="Xóa mục"
              @click="checklist.splice(index, 1)"
            >
              <Trash2 :size="16" />
            </button>
          </div>
          <button
            type="button"
            class="button ghost small"
            style="justify-self: start"
            @click="checklist.push('')"
          >
            <Plus :size="15" />Thêm mục
          </button>
        </div>
      </div>
      <div class="form-actions">
        <button type="button" class="button secondary" @click="close">
          Hủy</button
        ><button class="button" :disabled="busy || !title.trim()">
          {{ busy ? 'Đang lưu…' : target ? 'Giao việc' : 'Lưu nháp' }}
        </button>
      </div>
    </form>
  </ModalDialog>
</template>
