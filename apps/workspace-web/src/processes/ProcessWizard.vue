<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { computed, ref } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { ArrowLeft, ArrowRight, Check, Rocket } from 'lucide-vue-next'
import type { ApprovalStep, FormField, FormTemplate, User } from '@dx/web-shared/types.ts'
import type { Page } from '@dx/web-shared/api.ts'
import { errorText, newIntent } from '@dx/web-shared/api.ts'
import ModalDialog from '@dx/web-shared/components/ModalDialog.vue'
import { api } from '../api'
import { toast } from '../ui/toast'
import { confirmDiscard } from '../ui/unsaved'
import ProcessDiagram from '../packages/ProcessDiagram.vue'
import { ROLE_LABEL } from '../packages/model'
import FormDesigner from './FormDesigner.vue'

/**
 * One kind of dossier, set up on one screen: what it asks, who approves in what order and by
 * when, what must be attached. Saving creates the form and the process version together;
 * changing a process makes a new version so dossiers already filed keep the rules they had.
 */
export interface ProcessDraft {
  name: string
  description: string
  fields: FormField[]
  steps: ApprovalStep[]
  files: number
  roles: string[]
}
const props = defineProps<{
  mode: 'create' | 'revise'
  packageId?: string
  initial?: ProcessDraft
  users: User[]
  userName: (id: string) => string
}>()
const emit = defineEmits<{ close: []; saved: [packageId: string] }>()

const blank: ProcessDraft = {
  name: '',
  description: '',
  fields: [],
  steps: [{ label: 'Lãnh đạo phòng phê duyệt', resolver: 'department_manager', due_hours: 48 }],
  files: 0,
  roles: [],
}
// Query data and props are reactive proxies, which structuredClone refuses; JSON copies plain data.
function copy<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}
const draft = ref<ProcessDraft>(copy(props.initial ?? blank))
const opened = JSON.stringify(draft.value)
const publishNow = ref(true)
const stepIndex = ref(props.mode === 'revise' ? 1 : 0)
const busy = ref(false)
const error = ref('')
const TITLES = ['Thông tin', 'Trường thông tin', 'Bước duyệt', 'Quy định khi trình', 'Xem lại']

// Starting from a process already in use saves retyping a similar one.
interface ActiveVersion {
  id: string
  package_name: string
  form_id: string
  approval_steps: ApprovalStep[]
  required_file_count: number
}
const sources = useQuery({
  queryKey: ['business-packages', 'active-versions'],
  queryFn: () => api.request<Page<ActiveVersion>>('/business-packages/active-versions'),
  enabled: props.mode === 'create',
})
const forms = useQuery({ queryKey: ['forms'], queryFn: () => api.request<Page<FormTemplate>>('/forms') })
function startFrom(versionId: string) {
  const source = sources.data.value?.items.find((item) => item.id === versionId)
  const form = forms.data.value?.items.find((item) => item.id === source?.form_id)
  if (!source || !form) return
  draft.value.fields = copy(form.fields)
  draft.value.steps = copy(source.approval_steps)
  draft.value.files = source.required_file_count
  if (!draft.value.description) draft.value.description = form.description ?? ''
  toast.success(`Đã chép trường và bước duyệt từ “${source.package_name}”. Sửa lại cho quy trình mới.`)
}

const problem = computed(() => {
  const d = draft.value
  if (stepIndex.value === 0 && !d.name.trim()) return 'Đặt tên cho quy trình.'
  if (stepIndex.value === 1) {
    if (!d.fields.length) return 'Thêm ít nhất một trường thông tin.'
    if (d.fields.some((f) => !f.label.trim() || !/^[a-z][a-z0-9_]*$/.test(f.key))) return 'Mỗi trường cần tên và mã hợp lệ.'
    if (new Set(d.fields.map((f) => f.key)).size !== d.fields.length) return 'Có hai trường trùng mã.'
    if (d.fields.some((f) => f.type === 'select' && !f.options?.length)) return 'Trường chọn giá trị cần ít nhất một lựa chọn.'
  }
  if (stepIndex.value === 2) {
    if (!d.steps.length) return 'Thêm ít nhất một bước duyệt.'
    if (d.steps.some((s) => !s.label.trim() || (s.resolver === 'user' && !s.user_id))) return 'Mỗi bước cần tên và người duyệt.'
    if (!d.steps.some((s) => !s.condition)) return 'Cần ít nhất một bước luôn áp dụng, để hồ sơ nào cũng có người duyệt.'
  }
  return ''
})
function next() {
  if (problem.value) return
  stepIndex.value += 1
}
function close() {
  if (!busy.value && confirmDiscard(JSON.stringify(draft.value) !== opened)) emit('close')
}
async function save() {
  busy.value = true
  error.value = ''
  const d = draft.value
  const steps = d.steps.map((s) => ({ ...s, user_id: s.resolver === 'user' ? s.user_id : undefined }))
  try {
    if (props.mode === 'create') {
      const created = await api.request<{ id: string }>('/processes', {
        method: 'POST',
        headers: { 'Idempotency-Key': newIntent() },
        body: JSON.stringify({
          name: d.name.trim(),
          description: d.description,
          fields: d.fields,
          approval_steps: steps,
          required_file_count: d.files,
          allowed_roles: d.roles,
          publish: publishNow.value,
        }),
      })
      toast.success(publishNow.value ? 'Đã tạo và phát hành quy trình' : 'Đã tạo quy trình (bản nháp)')
      emit('saved', created.id)
    } else {
      await api.request(`/business-packages/${props.packageId}/revise`, {
        method: 'POST',
        headers: { 'Idempotency-Key': newIntent() },
        body: JSON.stringify({
          description: d.description,
          fields: d.fields,
          approval_steps: steps,
          required_file_count: d.files,
          publish: publishNow.value,
        }),
      })
      toast.success(
        publishNow.value
          ? 'Đã phát hành phiên bản mới. Hồ sơ đã lập trước đó giữ quy trình cũ.'
          : 'Đã tạo phiên bản mới (bản nháp)',
      )
      emit('saved', props.packageId!)
    }
  } catch (cause) {
    error.value = errorText(cause)
  } finally {
    busy.value = false
  }
}
function toggleRole(role: string) {
  const roles = draft.value.roles
  draft.value.roles = roles.includes(role) ? roles.filter((r) => r !== role) : [...roles, role]
}
</script>
<template>
  <ModalDialog :title="mode === 'create' ? 'Tạo quy trình' : `Sửa quy trình “${draft.name}”`" wide @close="close">
    <ol class="wizard-steps">
      <li
        v-for="(title, index) in TITLES"
        :key="title"
        :class="{ done: index < stepIndex, current: index === stepIndex }"
      >
        <span>{{ index < stepIndex ? '✓' : index + 1 }}</span>{{ title }}
      </li>
    </ol>
    <div v-if="error" class="notice error error-inline" role="alert">{{ error }}</div>

    <div v-if="stepIndex === 0" class="stack">
      <div class="field">
        <label for="process-name">Tên quy trình<span class="required"> *</span></label>
        <input
          id="process-name"
          v-model="draft.name"
          maxlength="200"
          :disabled="mode === 'revise'"
          placeholder="Ví dụ: Đề nghị mua sắm thiết bị"
          autofocus
        />
      </div>
      <div class="field">
        <label for="process-description">Dùng khi nào</label>
        <textarea id="process-description" v-model="draft.description" rows="2" maxlength="3000" />
      </div>
      <div v-if="mode === 'create' && sources.data.value?.items.length" class="field">
        <label for="process-source">Bắt đầu từ quy trình có sẵn (không bắt buộc)</label>
        <select id="process-source" @change="startFrom(($event.target as HTMLSelectElement).value)">
          <option value="">Bắt đầu trống</option>
          <option v-for="item in sources.data.value.items" :key="item.id" :value="item.id">{{ item.package_name }}</option>
        </select>
      </div>
    </div>

    <FormDesigner v-else-if="stepIndex === 1" v-model:fields="draft.fields" v-model:steps="draft.steps" section="fields" :users="users" />
    <FormDesigner v-else-if="stepIndex === 2" v-model:fields="draft.fields" v-model:steps="draft.steps" section="steps" :users="users" />

    <div v-else-if="stepIndex === 3" class="stack">
      <div class="field">
        <label for="process-files">Số tài liệu tối thiểu khi trình</label>
        <input id="process-files" v-model.number="draft.files" type="number" min="0" max="30" style="max-width: 140px" />
      </div>
      <div v-if="mode === 'create'" class="field">
        <span class="section-label">Vai trò được dùng quy trình này</span>
        <div class="ai-chips">
          <label v-for="(label, role) in ROLE_LABEL" :key="role" class="checkbox-label">
            <input type="checkbox" :checked="draft.roles.includes(role)" @change="toggleRole(role)" />{{ label }}
          </label>
        </div>
        <small class="muted">Không chọn vai trò nào nghĩa là mọi người có quyền tạo hồ sơ đều dùng được.</small>
      </div>
    </div>

    <div v-else class="stack">
      <ProcessDiagram :steps="draft.steps" :fields="draft.fields" :required-files="draft.files" :user-name="userName" />
      <div>
        <span class="section-label">Người lập hồ sơ sẽ nhập</span>
        <div class="field-chips">
          <span v-for="field in draft.fields" :key="field.key" class="tag"
            >{{ field.label }}<b v-if="field.required" class="required"> *</b></span
          >
        </div>
      </div>
      <label class="checkbox-label">
        <input v-model="publishNow" type="checkbox" />Phát hành ngay để dùng cho hồ sơ mới
      </label>
      <small class="muted">
        Hệ thống kiểm tra người duyệt và cấu hình trước khi phát hành. Muốn chạy thử với vài hồ sơ mẫu trước, bỏ chọn
        rồi vào tab “Chạy thử” của quy trình.
      </small>
    </div>

    <p v-if="problem" class="muted" role="status" style="margin-top: 12px">{{ problem }}</p>
    <div class="form-actions">
      <button v-if="stepIndex > (mode === 'revise' ? 1 : 0)" type="button" class="button secondary" :disabled="busy" @click="stepIndex -= 1">
        <ArrowLeft :size="16" />Quay lại
      </button>
      <button type="button" class="button secondary" :disabled="busy" @click="close">Hủy</button>
      <button v-if="stepIndex < TITLES.length - 1" type="button" class="button" :disabled="!!problem" @click="next">
        Tiếp<ArrowRight :size="16" />
      </button>
      <button v-else type="button" class="button" :disabled="busy" @click="save">
        <Rocket v-if="publishNow" :size="16" /><Check v-else :size="16" />{{
          busy ? 'Đang lưu…' : publishNow ? 'Lưu và phát hành' : 'Lưu bản nháp'
        }}
      </button>
    </div>
  </ModalDialog>
</template>
