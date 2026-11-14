<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { ref } from 'vue'
import type { ApprovalStep, FormField, User } from '@dx/web-shared/types.ts'
import { errorText } from '@dx/web-shared/api.ts'
import ModalDialog from '@dx/web-shared/components/ModalDialog.vue'
import { api } from '../api'
import { toast } from '../ui/toast'
import FormDesigner from '../processes/FormDesigner.vue'

/**
 * The questions a dossier asks, made while designing its process. Published forms never change in
 * place, so changing one makes a new form; dossiers already opened keep the one they used.
 */
const props = defineProps<{ name?: string; description?: string; fields?: FormField[] }>()
const emit = defineEmits<{ close: []; created: [formId: string] }>()
const name = ref(props.name ?? '')
const description = ref(props.description ?? '')
const fields = ref<FormField[]>(JSON.parse(JSON.stringify(props.fields ?? [])) as FormField[])
// Unused while a process is in force; the form needs them if its process is ever withdrawn.
const steps = ref<ApprovalStep[]>([{ label: 'Lãnh đạo phòng phê duyệt', resolver: 'department_manager' }])
const users: User[] = []
const busy = ref(false)
const error = ref('')

async function create() {
  busy.value = true
  error.value = ''
  try {
    const form = await api.request<{ id: string }>('/forms', {
      method: 'POST',
      body: JSON.stringify({
        name: name.value,
        description: description.value,
        fields: fields.value,
        approval_steps: steps.value,
      }),
    })
    toast.success(`Đã tạo biểu mẫu “${name.value}”`)
    emit('created', form.id)
  } catch (cause) {
    error.value = errorText(cause)
  } finally {
    busy.value = false
  }
}
</script>
<template>
  <ModalDialog :title="fields.length && props.fields ? 'Sửa trường thông tin' : 'Tạo biểu mẫu mới'" wide @close="emit('close')">
    <form class="stack" @submit.prevent="create">
      <p v-if="props.fields" class="muted">
        Biểu mẫu đã phát hành không sửa trực tiếp: hệ thống tạo biểu mẫu mới và gắn vào bản nháp này. Hồ sơ đã tạo vẫn dùng
        biểu mẫu cũ.
      </p>
      <div class="field">
        <label for="process-form-name">Tên biểu mẫu<span class="required"> *</span></label>
        <input id="process-form-name" v-model="name" required maxlength="200" />
      </div>
      <div class="field">
        <label for="process-form-description">Mô tả</label>
        <textarea id="process-form-description" v-model="description" rows="2" maxlength="3000" />
      </div>
      <FormDesigner v-model:fields="fields" v-model:steps="steps" section="fields" :users="users" />
      <div v-if="error" class="notice error error-inline" role="alert">{{ error }}</div>
      <div class="form-actions">
        <button type="button" class="button secondary" @click="emit('close')">Hủy</button>
        <button class="button" :disabled="busy || !fields.length">{{ busy ? 'Đang tạo…' : 'Tạo biểu mẫu' }}</button>
      </div>
    </form>
  </ModalDialog>
</template>
