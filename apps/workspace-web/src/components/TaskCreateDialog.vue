<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { FileText, FolderOpen, Plus, Sparkles, Trash2, Upload, X } from 'lucide-vue-next'
import { api } from '../api'
import { ApiError, errorText } from '@dx/web-shared/api.ts'
import type { Task } from '@dx/web-shared/types.ts'
import ModalDialog from '@dx/web-shared/components/ModalDialog.vue'
import { toast } from '../ui/toast'
import { confirmDiscard } from '../ui/unsaved'
import { useAi } from '../ai/useAi'
import DrivePicker from './DrivePicker.vue'
import PeoplePicker from './pickers/PeoplePicker.vue'
import type { PickerOption } from './pickers/filter'
import { mergeIds, uploadToDrive, type AttachedFile } from './attachments'
import { uploadLabel } from './workForms'
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
const departmentName = computed(() => new Map((options.data.value?.departments ?? []).map((d) => [d.id, d.name])))
const members = computed(() => {
  const map = new Map<string, string[]>()
  for (const user of options.data.value?.users ?? [])
    if (user.department_id) map.set(user.department_id, [...(map.get(user.department_id) ?? []), user.id])
  return map
})
const memberCount = (id: string) => `${members.value.get(id)?.length ?? 0} người`
const personOptions = (valueOf: (id: string) => string): PickerOption[] =>
  (options.data.value?.users ?? []).map((u) => ({
    value: valueOf(u.id),
    label: u.display_name,
    secondary: (u.department_id && departmentName.value.get(u.department_id)) || undefined,
    group: 'Cá nhân',
    kind: 'user',
    userId: u.id,
  }))
const targetOptions = computed<PickerOption[]>(() => [
  { value: '', label: 'Lưu nháp, chưa giao', group: '', kind: 'special' },
  ...personOptions((id) => `user:${id}`),
  ...(options.data.value?.departments ?? []).map((d) => ({
    value: `dept:${d.id}`,
    label: d.name,
    secondary: `${memberCount(d.id)} · trưởng đơn vị phân công tiếp`,
    group: 'Đơn vị',
    kind: 'dept' as const,
  })),
])
const watcherOptions = computed<PickerOption[]>(() => [
  ...personOptions((id) => id),
  ...(options.data.value?.departments ?? [])
    .filter((d) => members.value.has(d.id))
    .map((d) => ({
      value: `dept:${d.id}`,
      label: d.name,
      secondary: memberCount(d.id),
      group: 'Cả phòng',
      kind: 'dept' as const,
      memberIds: members.value.get(d.id),
    })),
])
const title = ref(props.defaultTitle ?? '')
const description = ref('')
const target = ref('')
const priority = ref<Task['priority']>('normal')
const dueAt = ref('')
const checklist = ref<string[]>([])
const watcherIds = ref<string[]>([])
// Brief, templates or data the person will need, attached before the task is sent.
const attachments = ref<AttachedFile[]>([])
const uploading = ref(false)
const progress = ref({ done: 0, total: 0 })
const picking = ref(false)
const filePicker = ref<HTMLInputElement>()
async function uploadPicked(event: Event) {
  const input = event.target as HTMLInputElement
  const chosen = [...(input.files ?? [])]
  input.value = ''
  if (!chosen.length) return
  uploading.value = true
  progress.value = { done: 0, total: chosen.length }
  try {
    // Files that went up before a failure stay attached; only the rest need picking again.
    for (const file of chosen) {
      const uploaded = await uploadToDrive(file)
      if (!attachments.value.some((f) => f.id === uploaded.id)) attachments.value.push(uploaded)
      progress.value = { ...progress.value, done: progress.value.done + 1 }
    }
  } catch (cause) {
    toast.error(cause)
  } finally {
    uploading.value = false
  }
}
function attachPicked(files: AttachedFile[]) {
  picking.value = false
  const ids = mergeIds(attachments.value.map((f) => f.id), files.map((f) => f.id))
  attachments.value = ids.map((id) => attachments.value.find((f) => f.id === id) ?? files.find((f) => f.id === id)!)
}
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
    attachments.value.length > 0 ||
    watcherIds.value.length > 0,
)
async function close() {
  if (!busy.value && await confirmDiscard(dirty.value)) emit('close')
}
// Indexed by line so focus lands on the line just added (a v-for ref array keeps no order).
const checklistInputs: (HTMLInputElement | null)[] = []
/** Enter in a checklist line adds the next line instead of sending the whole form. */
async function addChecklistItem(after = checklist.value.length - 1) {
  checklist.value.splice(after + 1, 0, '')
  await nextTick()
  checklistInputs[after + 1]?.focus()
}
const submitBlocked = computed(() =>
  !title.value.trim() ? 'Nhập tên công việc trước.' : uploading.value ? 'Chờ tải tệp xong.' : '',
)
async function submit() {
  if (busy.value || submitBlocked.value) return
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
        file_ids: attachments.value.map((f) => f.id),
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
      <div v-if="ai.on('task_parse')" class="ai-card task-parse">
        <label class="ai-title" for="task-sentence"><Sparkles :size="16" />Giao việc bằng một câu</label>
        <div class="inline-actions task-parse-row">
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
        <div class="field full-width">
          <label for="task-target">Người / đơn vị nhận</label>
          <PeoplePicker
            id="task-target"
            v-model="target"
            :options="targetOptions"
            :disabled="busy"
            placeholder="Tìm theo tên hoặc đơn vị…"
            recent-key="dx.picker.task-target"
          />
          <small>{{ scopeHint }} Để trống để lưu nháp, giao sau.</small>
        </div>
        <div class="field">
          <label for="task-due">Hạn hoàn thành</label
          ><input id="task-due" v-model="dueAt" type="datetime-local" /><small>Có thể để trống nếu chưa có hạn.</small>
        </div>
        <div class="field">
          <label for="task-priority">Mức ưu tiên</label
          ><select id="task-priority" v-model="priority">
            <option value="low">Thấp</option>
            <option value="normal">Bình thường</option>
            <option value="high">Cao</option>
            <option value="urgent">Khẩn</option>
          </select>
          <small>Việc khẩn được đánh dấu nổi bật cho người nhận.</small>
        </div>
        <div class="field full-width">
          <label for="task-watchers">Người theo dõi</label>
          <PeoplePicker
            id="task-watchers"
            v-model="watcherIds"
            multiple
            :options="watcherOptions"
            :disabled="busy"
            placeholder="Thêm người theo dõi…"
            recent-key="dx.picker.task-watchers"
          />
          <small>Theo dõi tiến độ mà không phải thực hiện. Chọn tên một phòng để thêm cả phòng.</small>
        </div>
        <div class="field full-width">
          <span id="task-files-label" class="field-label">Tài liệu đính kèm</span>
          <div v-if="attachments.length" class="ai-chips" role="list" aria-labelledby="task-files-label">
            <span v-for="file in attachments" :key="file.id" class="file-chip" role="listitem"
              ><FileText :size="14" aria-hidden="true" /><span class="file-chip-name" :title="file.name ?? ''">{{
                file.name
              }}</span
              ><button
                type="button"
                class="icon-button file-chip-remove"
                :aria-label="`Bỏ ${file.name}`"
                title="Bỏ tệp này"
                @click="attachments = attachments.filter((f) => f.id !== file.id)"
              >
                <X :size="13" /></button
            ></span>
          </div>
          <div class="inline-actions">
            <button type="button" class="button ghost small" :disabled="uploading" @click="filePicker?.click()">
              <Upload :size="15" />{{ uploading ? uploadLabel(progress.done, progress.total) : 'Tải tệp lên' }}
            </button>
            <button type="button" class="button ghost small" :disabled="uploading" @click="picking = true">
              <FolderOpen :size="15" />Chọn từ kho tài liệu
            </button>
            <input ref="filePicker" type="file" multiple hidden @change="uploadPicked" />
          </div>
          <small class="muted">Người nhận việc mở được các tệp này qua công việc, không cần chia sẻ riêng.</small>
        </div>
        <div class="field full-width">
          <span class="field-label">Checklist cần hoàn thành trước khi nộp</span>
          <div v-for="(_, index) in checklist" :key="index" class="checklist-edit">
            <input
              :ref="(el) => (checklistInputs[index] = el as HTMLInputElement)"
              v-model="checklist[index]"
              :aria-label="`Mục ${index + 1}`"
              maxlength="300"
              placeholder="Ví dụ: Gửi bản dự thảo cho phòng Kế hoạch"
              @keydown.enter.prevent="addChecklistItem(index)"
            /><button
              type="button"
              class="icon-button"
              :aria-label="`Xóa mục ${index + 1}`"
              title="Xóa mục"
              @click="checklist.splice(index, 1)"
            >
              <Trash2 :size="16" />
            </button>
          </div>
          <button type="button" class="button ghost small checklist-add" @click="addChecklistItem()">
            <Plus :size="15" />Thêm mục
          </button>
        </div>
      </div>
      <div class="form-actions">
        <button type="button" class="button secondary" :disabled="busy" @click="close">
          Hủy</button
        ><button class="button" :disabled="busy || !!submitBlocked" :title="submitBlocked">
          {{ busy ? (target ? 'Đang giao…' : 'Đang lưu…') : target ? 'Giao việc' : 'Lưu nháp' }}
        </button>
      </div>
    </form>
  </ModalDialog>
  <DrivePicker v-if="picking" :exclude="attachments.map((f) => f.id)" @close="picking = false" @picked="attachPicked" />
</template>
<style scoped>
#task-due {
  min-width: 0;
}
.task-parse {
  margin-bottom: 20px;
}
.task-parse-row {
  margin-top: 8px;
  flex-wrap: nowrap;
}
.task-parse-row input {
  flex: 1;
  min-width: 0;
}
.field-label {
  font-weight: 600;
  font-size: 0.9375rem;
}
.file-chip-name {
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.file-chip-remove {
  width: 28px;
  height: 28px;
}
.checklist-add {
  align-self: flex-start;
}
@media (max-width: 640px) {
  .task-parse-row {
    flex-wrap: wrap;
  }
}
</style>
