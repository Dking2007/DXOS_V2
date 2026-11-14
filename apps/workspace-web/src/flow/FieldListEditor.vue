<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { Plus } from 'lucide-vue-next'
import { fieldKey } from '@dx/web-shared/forms.ts'

/** The fields a step asks someone to fill in; each keeps the code later steps read it by. */
export interface StepField {
  key: string
  label: string
  type: string
  required: boolean
  options: string[]
}
const props = defineProps<{ fields: StepField[]; reference: string }>()
const emit = defineEmits<{ update: [fields: StepField[]] }>()

function change(index: number, values: Partial<StepField>) {
  emit('update', props.fields.map((item, i) => (i === index ? { ...item, ...values } : item)))
}
function rename(index: number, label: string) {
  const current = props.fields[index]
  const placeholder = !current?.key || /^truong_\d+$/.test(current.key)
  change(index, { label, ...(placeholder ? { key: fieldKey(label) } : {}) })
}
function add() {
  const key = `truong_${props.fields.length + 1}`
  emit('update', [...props.fields, { key, label: '', type: 'text', required: false, options: [] }])
}
function remove(index: number) {
  emit('update', props.fields.filter((_, i) => i !== index))
}
const text = (event: Event) => (event.target as HTMLInputElement).value
</script>
<template>
  <div v-for="(field, index) in fields" :key="index" class="condition-card">
    <input :value="field.label" :aria-label="`Tên trường ${index + 1}`" placeholder="Tên trường" @change="rename(index, text($event))" />
    <select :value="field.type" :aria-label="`Kiểu trường ${index + 1}`" @change="change(index, { type: text($event) })">
      <option value="text">Chữ</option>
      <option value="textarea">Đoạn văn</option>
      <option value="number">Số</option>
      <option value="date">Ngày</option>
      <option value="select">Danh sách chọn</option>
    </select>
    <input
      v-if="field.type === 'select'"
      :value="field.options.join(', ')"
      placeholder="Các lựa chọn, cách nhau bởi dấu phẩy"
      :aria-label="`Lựa chọn của trường ${index + 1}`"
      @change="change(index, { options: text($event).split(',').map((item) => item.trim()).filter(Boolean) })"
    />
    <label class="checkbox-label">
      <input type="checkbox" :checked="field.required" @change="change(index, { required: ($event.target as HTMLInputElement).checked })" /> Bắt buộc
    </label>
    <small class="muted">Đọc ở bước sau: <code>{{ '{' + reference + '.' + field.key + '}' }}</code></small>
    <button type="button" class="button ghost small" @click="remove(index)">Xóa trường</button>
  </div>
  <button type="button" class="button secondary small" @click="add"><Plus :size="14" />Thêm trường</button>
</template>
