<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { computed, ref } from 'vue'
import { ArrowLeft, ArrowRight, Check, Copy, FileText } from 'lucide-vue-next'
import { api } from '../api'
import { errorText, newIntent } from '@dx/web-shared/api.ts'
import type { FormTemplate } from '@dx/web-shared/types.ts'
import ModalDialog from '@dx/web-shared/components/ModalDialog.vue'
import { toast } from '../ui/toast'
import { confirmDiscard } from '../ui/unsaved'
import ProcessDiagram from './ProcessDiagram.vue'
import { ROLE_LABEL } from './model'
const props = defineProps<{
  /** "package" creates a new package; "version" adds a version to `packageId`. */
  mode: 'package' | 'version'
  packageId?: string
  forms: FormTemplate[]
  templates: { id: string; name: string; active_version_id: string | null }[]
  initialFormId?: string
  initialFiles?: number
  userName: (id: string) => string
}>()
const emit = defineEmits<{ close: []; created: [packageId: string] }>()
const stepIndex = ref(props.mode === 'version' ? 1 : 0)
const name = ref('')
const description = ref('')
const template = ref('')
const formId = ref(props.initialFormId ?? '')
const requiredFiles = ref(props.initialFiles ?? 0)
const roles = ref<string[]>([])
const busy = ref(false)
const error = ref<unknown>(null)
const form = computed(() => props.forms.find((f) => f.id === formId.value))
const titles = ['Thông tin quy trình', 'Chọn biểu mẫu', 'Quy định khi trình']
const canNext = computed(() =>
  stepIndex.value === 0 ? !!name.value.trim() : stepIndex.value === 1 ? !!form.value : true,
)
const unconditional = computed(() => form.value?.approval_steps.some((s) => !s.condition) ?? false)
function toggleRole(role: string) {
  roles.value = roles.value.includes(role) ? roles.value.filter((r) => r !== role) : [...roles.value, role]
}
const dirty = computed(
  () =>
    !!name.value.trim() ||
    !!description.value.trim() ||
    !!template.value ||
    formId.value !== (props.initialFormId ?? '') ||
    requiredFiles.value !== (props.initialFiles ?? 0) ||
    roles.value.length > 0,
)
function close() {
  if (!busy.value && confirmDiscard(dirty.value)) emit('close')
}
async function submit() {
  busy.value = true
  error.value = null
  try {
    if (props.mode === 'version') {
      await api.request(`/business-packages/${props.packageId}/versions`, {
        method: 'POST',
        headers: { 'Idempotency-Key': newIntent() },
        body: JSON.stringify({ form_id: formId.value, required_file_count: requiredFiles.value }),
      })
      toast.success('Đã tạo phiên bản mới (bản nháp)')
      emit('created', props.packageId!)
    } else if (template.value) {
      const source = props.templates.find((t) => t.id === template.value)!
      const created = await api.request<{ id: string }>('/business-packages/from-template', {
        method: 'POST',
        headers: { 'Idempotency-Key': newIntent() },
        body: JSON.stringify({ version_id: source.active_version_id, name: name.value.trim() }),
      })
      toast.success('Đã tạo quy trình từ mẫu có sẵn')
      emit('created', created.id)
    } else {
      const created = await api.request<{ id: string }>('/business-packages', {
        method: 'POST',
        headers: { 'Idempotency-Key': newIntent() },
        body: JSON.stringify({
          name: name.value.trim(),
          description: description.value,
          form_id: formId.value,
          required_file_count: requiredFiles.value,
          allowed_roles: roles.value,
        }),
      })
      toast.success('Đã tạo quy trình')
      emit('created', created.id)
    }
  } catch (cause) {
    error.value = cause
  } finally {
    busy.value = false
  }
}
</script>
<template>
  <ModalDialog :title="mode === 'version' ? 'Tạo phiên bản mới' : 'Chuyển biểu mẫu thành quy trình'" wide @close="close">
    <ol v-if="mode === 'package' && !template" class="wizard-steps">
      <li v-for="(title, index) in titles" :key="title" :class="{ done: index < stepIndex, current: index === stepIndex }">
        <span>{{ index < stepIndex ? '✓' : index + 1 }}</span>{{ title }}
      </li>
    </ol>
    <div v-if="error" class="notice error error-inline">{{ errorText(error) }}</div>

    <div v-if="stepIndex === 0" class="stack">
      <div class="field">
        <label for="pkg-name">Tên quy trình<span class="required"> *</span></label
        ><input id="pkg-name" v-model="name" maxlength="200" placeholder="Ví dụ: Đề nghị mua sắm thiết bị" autofocus />
      </div>
      <div class="field">
        <label for="pkg-desc">Mục đích, phạm vi áp dụng</label
        ><textarea id="pkg-desc" v-model="description" rows="2" :disabled="!!template" />
      </div>
      <div v-if="templates.length" class="field">
        <label>Bắt đầu từ</label>
        <div class="choice-grid">
          <button type="button" class="choice-card" :class="{ active: !template }" @click="template = ''">
            <FileText :size="18" /><strong>Gói trống</strong><small>Tự chọn biểu mẫu và quy định</small>
          </button>
          <button
            v-for="item in templates"
            :key="item.id"
            type="button"
            class="choice-card"
            :class="{ active: template === item.id }"
            @click="template = item.id"
          >
            <Copy :size="18" /><strong>{{ item.name }}</strong><small>Sao chép cấu hình đang dùng</small>
          </button>
        </div>
        <small v-if="template">Bản sao là quy trình nháp riêng; cần kiểm tra và chạy thử lại trước khi phát hành.</small>
      </div>
    </div>

    <div v-else-if="stepIndex === 1" class="stack">
      <p class="muted">
        Biểu mẫu quyết định trường thông tin và các bước duyệt. Sau khi tạo, đổi trường hay bước duyệt bằng nút
        “Sửa quy trình”.
      </p>
      <div v-if="!forms.length" class="notice warning">Chưa có biểu mẫu đã phát hành.</div>
      <div class="choice-grid">
        <button
          v-for="item in forms"
          :key="item.id"
          type="button"
          class="choice-card"
          :class="{ active: formId === item.id }"
          @click="formId = item.id"
        >
          <FileText :size="18" /><strong>{{ item.name }}</strong
          ><small>{{ item.fields.length }} trường · {{ item.approval_steps.length }} bước duyệt</small>
        </button>
      </div>
      <template v-if="form">
        <span class="section-label">Quy trình duyệt của biểu mẫu này</span>
        <ProcessDiagram :steps="form.approval_steps" :fields="form.fields" :required-files="requiredFiles" :user-name="userName" />
        <div v-if="!unconditional" class="notice warning">
          Mọi bước đều có điều kiện — quy trình cần ít nhất một bước luôn áp dụng để hồ sơ nào cũng có người duyệt.
        </div>
      </template>
    </div>

    <div v-else class="stack">
      <div class="field">
        <label for="pkg-files">Số tài liệu tối thiểu khi trình</label
        ><input id="pkg-files" v-model.number="requiredFiles" type="number" min="0" max="30" style="max-width: 140px" />
      </div>
      <div v-if="mode === 'package'" class="field">
        <label>Ai được dùng gói này để tạo hồ sơ</label>
        <div class="chip-select">
          <button v-for="(label, key) in ROLE_LABEL" :key="key" type="button" :class="{ active: roles.includes(key) }" @click="toggleRole(key)">
            {{ label }}
          </button>
        </div>
        <small>{{ roles.length ? 'Chỉ các vai trò đã chọn.' : 'Không chọn = mọi vai trò có quyền tạo hồ sơ.' }}</small>
      </div>
      <div class="notice">
        <Check :size="18" /><span
          >Gói được tạo ở dạng <strong>bản nháp</strong>. Tiếp theo: kiểm tra cấu hình → chạy thử kịch bản → phát hành.</span
        >
      </div>
    </div>

    <div class="form-actions">
      <button v-if="stepIndex > (mode === 'version' ? 1 : 0) && !template" type="button" class="button secondary" @click="stepIndex--">
        <ArrowLeft :size="15" />Quay lại
      </button>
      <button type="button" class="button secondary" @click="close">Hủy</button>
      <button v-if="stepIndex < 2 && !template" type="button" class="button" :disabled="!canNext" @click="stepIndex++">
        Tiếp <ArrowRight :size="15" />
      </button>
      <button v-else type="button" class="button" :disabled="busy || !canNext || (!template && !unconditional)" @click="submit">
        {{ busy ? 'Đang tạo…' : mode === 'version' ? 'Tạo phiên bản' : 'Tạo gói' }}
      </button>
    </div>
  </ModalDialog>
</template>
