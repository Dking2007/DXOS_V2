<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { computed, ref } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { Plus, Trash2 } from 'lucide-vue-next'
import { api } from '../api'
import { ApiError, errorText } from '@dx/web-shared/api.ts'
import type { Task } from '@dx/web-shared/types.ts'
import ModalDialog from '@dx/web-shared/components/ModalDialog.vue'
import { toast } from '../ui/toast'
import { confirmDiscard } from '../ui/unsaved'
const props = defineProps<{
  parentId?: string
  caseId?: string
  source?: { type: string; id?: string; label?: string }
  defaultTitle?: string
  heading?: string
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
