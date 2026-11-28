<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { computed, ref } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { FileText, Upload, X } from 'lucide-vue-next'
import type { ApprovalTask, User } from '@dx/web-shared/types.ts'
import { errorText, newIntent, type Page } from '@dx/web-shared/api.ts'
import ModalDialog from '@dx/web-shared/components/ModalDialog.vue'
import { api } from '../api'
import { toast } from '../ui/toast'
import { uploadToDrive } from './attachments'
import { confirmDiscard } from '../ui/unsaved'
import { reasonMissing, uploadLabel } from './workForms'
import PeoplePicker from './pickers/PeoplePicker.vue'
import { asText, userOptions } from './pickers/options'

/**
 * Answering a flow's request: what it asks to be handed in, the decision when none was picked on
 * the screen behind (a request about a task or post has no dossier page), or passing it on.
 */
const props = defineProps<{ task: ApprovalTask; mode: 'answer' | 'forward'; decision?: string }>()
const emit = defineEmits<{ close: []; done: [] }>()
const busy = ref(false)
const error = ref('')
const intent = newIntent()
const values = ref<Record<string, unknown>>({})
const uploads = ref<{ id: string; name: string | null }[]>([])
const reason = ref('')
const LABELS: Record<string, string> = {
  approve: 'Duyệt',
  return: 'Trả lại',
  reject: 'Từ chối',
  submit: 'Xác nhận',
}
const options = computed(() => props.task.options ?? ['approve', 'return', 'reject'])
const chosen = ref(props.decision ?? options.value[0] ?? 'approve')
const label = (option: string) =>
  props.task.kind === 'opinion' ? (option === 'approve' ? 'Đồng ý' : 'Không đồng ý') : (LABELS[option] ?? option)
const positive = computed(() => chosen.value === 'approve' || chosen.value === 'submit')
const fields = computed(() =>
  positive.value ? [...(props.task.step?.fields ?? []), ...(props.task.step?.result_fields ?? [])] : [],
)
const needFiles = computed(() => (positive.value ? (props.task.step?.require_files ?? 0) : 0))
const takesFiles = computed(() => positive.value && (needFiles.value > 0 || !!props.task.step?.allow_files))
const title = computed(() => {
  if (props.mode === 'forward') return 'Chuyển người xử lý'
  return props.task.label || 'Xử lý yêu cầu'
})

const users = useQuery({
  queryKey: ['users'],
  queryFn: () => api.request<Page<User>>('/users'),
  enabled: computed(() => props.mode === 'forward'),
})
const target = ref('')
const targetOptions = computed(() => userOptions(users.data.value?.items ?? [], 'Chọn người…'))

const picker = ref<HTMLInputElement>()
const progress = ref({ done: 0, total: 0 })
async function pick(event: Event) {
  const input = event.target as HTMLInputElement
  const picked = [...(input.files ?? [])]
  input.value = ''
  if (!picked.length) return
  busy.value = true
  error.value = ''
  progress.value = { done: 0, total: picked.length }
  try {
    for (const file of picked) {
      uploads.value.push(await uploadToDrive(file))
      progress.value = { ...progress.value, done: progress.value.done + 1 }
    }
  } catch (cause) {
    error.value = errorText(cause)
  } finally {
    busy.value = false
    progress.value = { done: 0, total: 0 }
  }
}
/** Why the send button cannot go through yet; shown as its tooltip. */
const blocked = computed(() => {
  if (progress.value.total) return 'Chờ tải tệp xong.'
  if (props.mode === 'forward') return target.value ? '' : 'Chọn người nhận.'
  if (reasonMissing(!positive.value, reason.value)) return 'Nêu lý do trước khi gửi.'
  if (uploads.value.length < needFiles.value) return `Cần đính kèm ít nhất ${needFiles.value} tệp.`
  return ''
})
const dirty = computed(
  () =>
    !!reason.value.trim() ||
    !!target.value ||
    uploads.value.length > 0 ||
    Object.values(values.value).some((value) => value !== '' && value != null),
)
async function close() {
  if (!busy.value && await confirmDiscard(dirty.value)) emit('close')
}
async function send() {
  if (busy.value || blocked.value) return
  busy.value = true
  error.value = ''
  try {
    if (props.mode === 'forward') {
      await api.request(`/approval-tasks/${props.task.id}/forward`, {
        method: 'POST',
        body: JSON.stringify({ expected_revision: props.task.revision, user_id: target.value, reason: reason.value }),
      })
      toast.success('Đã chuyển người xử lý')
    } else {
      await api.request(`/approval-tasks/${props.task.id}/decisions`, {
        method: 'POST',
        headers: { 'Idempotency-Key': intent },
        body: JSON.stringify({
          expected_revision: props.task.revision,
          decision: chosen.value,
          reason: reason.value,
          values: positive.value ? values.value : {},
          file_ids: positive.value ? uploads.value.map((file) => file.id) : [],
        }),
      })
      toast.success('Đã ghi nhận')
    }
    emit('done')
  } catch (cause) {
    error.value = errorText(cause)
  } finally {
    busy.value = false
  }
}
</script>
<template>
  <ModalDialog :title="title" @close="close">
    <form class="stack" @submit.prevent="send">
      <div v-if="error" class="notice error error-inline" role="alert">{{ error }}</div>
      <template v-if="mode === 'forward'">
        <div class="field">
          <label for="forward-user">Chuyển cho<span class="required"> *</span></label>
          <PeoplePicker id="forward-user" :model-value="target" :options="targetOptions" placeholder="Chọn người…" :disabled="busy" @update:model-value="target = asText($event)" />
        </div>
        <div class="field">
          <label for="forward-reason">Lý do</label>
          <textarea id="forward-reason" v-model="reason" rows="2" maxlength="500" :disabled="busy" />
        </div>
      </template>
      <template v-else>
        <p v-if="task.instructions" class="muted">{{ task.instructions }}</p>
        <div v-if="!decision && options.length > 1" class="field">
          <label for="step-decision">Quyết định</label>
          <select id="step-decision" v-model="chosen">
            <option v-for="option in options" :key="option" :value="option">{{ label(option) }}</option>
          </select>
        </div>
        <div v-for="field in fields" :key="field.key" class="field">
          <label :for="`step-${field.key}`">{{ field.label }}<span v-if="field.required" class="required"> *</span></label>
          <textarea v-if="field.type === 'textarea'" :id="`step-${field.key}`" v-model="values[field.key] as string" rows="3" :required="field.required" />
          <select v-else-if="field.type === 'select'" :id="`step-${field.key}`" v-model="values[field.key]" :required="field.required">
            <option value="">Chọn…</option>
            <option v-for="option in field.options" :key="option" :value="option">{{ option }}</option>
          </select>
          <input v-else :id="`step-${field.key}`" v-model="values[field.key]" :type="field.type" :required="field.required" />
        </div>
        <div v-if="takesFiles" class="field">
          <span class="step-files-label">Tệp kết quả<span v-if="needFiles" class="required"> *</span></span>
          <div v-if="uploads.length" class="ai-chips" role="list">
            <span v-for="file in uploads" :key="file.id" class="file-chip" role="listitem"
              ><FileText :size="14" aria-hidden="true" /><span class="step-file-name" :title="file.name ?? ''">{{
                file.name
              }}</span
              ><button
                type="button"
                class="icon-button step-file-remove"
                :aria-label="`Bỏ ${file.name ?? 'tệp'}`"
                title="Bỏ tệp này"
                :disabled="busy"
                @click="uploads = uploads.filter((item) => item.id !== file.id)"
              >
                <X :size="13" /></button
            ></span>
          </div>
          <button type="button" class="button secondary small step-upload" :disabled="busy" @click="picker?.click()">
            <Upload :size="14" />{{ progress.total ? uploadLabel(progress.done, progress.total) : 'Đính kèm tệp' }}
          </button>
          <input ref="picker" type="file" multiple hidden @change="pick" />
          <small v-if="needFiles" class="muted">Cần ít nhất {{ needFiles }} tệp, đã có {{ uploads.length }}.</small>
        </div>
        <div v-if="!positive" class="field">
          <label for="step-reason">Lý do<span class="required"> *</span></label>
          <textarea id="step-reason" v-model="reason" rows="3" required maxlength="3000" :disabled="busy" />
        </div>
      </template>
      <div class="form-actions">
        <button type="button" class="button secondary" :disabled="busy" @click="close">Hủy</button>
        <button class="button" :class="{ danger: chosen === 'reject' && mode === 'answer' }" :disabled="busy || !!blocked" :title="blocked">
          {{
            busy && !progress.total
              ? 'Đang gửi…'
              : mode === 'forward'
                ? 'Chuyển'
                : positive
                  ? label(chosen)
                  : 'Gửi'
          }}
        </button>
      </div>
    </form>
  </ModalDialog>
</template>
<style scoped>
.step-files-label {
  font-weight: 600;
  font-size: 0.9375rem;
}
.step-upload {
  align-self: flex-start;
}
.step-file-name {
  max-width: 240px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.step-file-remove {
  width: 28px;
  height: 28px;
}
</style>
