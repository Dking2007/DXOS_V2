<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { ArrowDown, ArrowUp, Clock, Plus, Trash2 } from 'lucide-vue-next'
import type { ApprovalStep, FormField, User } from '@dx/web-shared/types.ts'
import { fieldKey } from '@dx/web-shared/forms.ts'
import { deadlineParts } from './deadline'

/** The fields a dossier asks for, or the approval steps it goes through, edited in place. */
defineProps<{ section: 'fields' | 'steps'; users: User[] }>()
const fields = defineModel<FormField[]>('fields', { required: true })
const steps = defineModel<ApprovalStep[]>('steps', { required: true })

function addField() {
  fields.value.push({ key: `truong_${fields.value.length + 1}`, label: '', type: 'text', required: false })
}
function autoKey(field: FormField) {
  if (/^truong_\d+$/.test(field.key) || !field.key) field.key = fieldKey(field.label)
}
function setOptions(field: FormField, event: Event) {
  field.options = (event.target as HTMLInputElement).value
    .split(',')
    .map((value) => value.trim())
    .filter(Boolean)
}
function move<T>(list: T[], index: number, change: number) {
  const other = index + change
  if (other < 0 || other >= list.length) return
  ;[list[index], list[other]] = [list[other]!, list[index]!]
}
function setDeadline(step: ApprovalStep, amount: number, unit: number) {
  step.due_hours = amount > 0 ? Math.round(amount * unit) : null
}
</script>
<template>
  <div v-if="section === 'fields'" class="stack">
    <div v-if="!fields.length" class="notice">Thêm các trường để người lập hồ sơ nhập đúng thông tin cần thiết.</div>
    <div v-for="(field, index) in fields" :key="index" class="builder-field">
      <div class="builder-field-head">
        <span>TRƯỜNG {{ index + 1 }}</span>
        <div class="inline-actions">
          <button type="button" class="icon-button" aria-label="Chuyển trường lên" :disabled="index === 0" @click="move(fields, index, -1)">
            <ArrowUp :size="14" /></button
          ><button
            type="button"
            class="icon-button"
            aria-label="Chuyển trường xuống"
            :disabled="index === fields.length - 1"
            @click="move(fields, index, 1)"
          >
            <ArrowDown :size="14" /></button
          ><button type="button" class="icon-button" aria-label="Xóa trường" @click="fields.splice(index, 1)">
            <Trash2 :size="15" />
          </button>
        </div>
      </div>
      <div class="form-grid" style="gap: 12px">
        <div class="field">
          <label :for="`label-${index}`">Nhãn hiển thị</label
          ><input :id="`label-${index}`" v-model="field.label" required @blur="autoKey(field)" />
        </div>
        <div class="field">
          <label :for="`type-${index}`">Loại trường</label
          ><select :id="`type-${index}`" v-model="field.type">
            <option value="text">Văn bản ngắn</option>
            <option value="textarea">Văn bản nhiều dòng</option>
            <option value="number">Số / số tiền</option>
            <option value="date">Ngày</option>
            <option value="select">Chọn một giá trị</option>
            <option value="checkbox">Xác nhận / checkbox</option>
          </select>
        </div>
        <div class="field">
          <label :for="`key-${index}`">Mã trường (tự tạo từ tên, không dấu)</label
          ><input :id="`key-${index}`" v-model="field.key" required pattern="[a-z][a-z0-9_]*" class="mono" />
        </div>
        <div v-if="field.type === 'select'" class="field">
          <label :for="`options-${index}`">Các lựa chọn, cách bằng dấu phẩy</label
          ><input :id="`options-${index}`" :value="field.options?.join(', ')" required @input="setOptions(field, $event)" />
        </div>
      </div>
      <label class="checkbox-label"><input v-model="field.required" type="checkbox" />Bắt buộc điền</label>
    </div>
    <button type="button" class="button secondary small" style="justify-self: start" @click="addField">
      <Plus :size="15" />Thêm trường
    </button>
  </div>

  <div v-else class="stack">
    <div v-for="(step, index) in steps" :key="index" class="step-editor">
      <div class="builder-field-head">
        <span>BƯỚC {{ index + 1 }}</span>
        <div class="inline-actions">
          <button type="button" class="icon-button" aria-label="Chuyển bước lên" :disabled="index === 0" @click="move(steps, index, -1)">
            <ArrowUp :size="14" /></button
          ><button
            type="button"
            class="icon-button"
            aria-label="Chuyển bước xuống"
            :disabled="index === steps.length - 1"
            @click="move(steps, index, 1)"
          >
            <ArrowDown :size="14" /></button
          ><button type="button" class="icon-button" aria-label="Xóa bước" @click="steps.splice(index, 1)">
            <Trash2 :size="15" />
          </button>
        </div>
      </div>
      <div class="form-grid">
        <div class="field full-width">
          <label :for="`step-label-${index}`">Tên bước</label><input :id="`step-label-${index}`" v-model="step.label" required />
        </div>
        <div class="field">
          <label :for="`step-resolver-${index}`">Người duyệt</label
          ><select :id="`step-resolver-${index}`" v-model="step.resolver">
            <option value="department_manager">Lãnh đạo phòng người gửi</option>
            <option value="user">Chỉ định thành viên</option>
          </select>
        </div>
        <div v-if="step.resolver === 'user'" class="field">
          <label :for="`step-user-${index}`">Thành viên nhận</label
          ><select :id="`step-user-${index}`" v-model="step.user_id" required>
            <option value="">Chọn người duyệt</option>
            <option v-for="user in users" :key="user.id" :value="user.id">{{ user.display_name }}</option>
          </select>
        </div>
        <div class="field">
          <label :for="`step-due-${index}`"><Clock :size="13" /> Thời hạn xử lý</label>
          <div class="inline-actions" style="flex-wrap: nowrap">
            <input
              :id="`step-due-${index}`"
              type="number"
              min="0"
              step="1"
              style="max-width: 90px"
              :value="deadlineParts(step.due_hours).amount || ''"
              placeholder="—"
              @change="setDeadline(step, Number(($event.target as HTMLInputElement).value), deadlineParts(step.due_hours).unit)"
            />
            <select
              :value="deadlineParts(step.due_hours).unit"
              aria-label="Đơn vị thời hạn"
              style="max-width: 110px"
              @change="
                setDeadline(step, deadlineParts(step.due_hours).amount || 1, Number(($event.target as HTMLSelectElement).value))
              "
            >
              <option :value="24">ngày</option>
              <option :value="1">giờ</option>
            </select>
          </div>
          <small class="muted">Tính từ lúc hồ sơ tới bước này. Để trống nếu không giới hạn.</small>
        </div>
      </div>
      <label class="checkbox-label"
        ><input
          type="checkbox"
          :checked="!!step.condition"
          @change="
            step.condition = ($event.target as HTMLInputElement).checked
              ? { field: fields[0]?.key || '', operator: 'gte', value: 0 }
              : undefined
          "
        />Chỉ thực hiện bước này khi thỏa điều kiện</label
      >
      <div v-if="step.condition" class="form-grid" style="margin-top: 13px">
        <div class="field">
          <label
            >Trường điều kiện<select v-model="step.condition.field" required>
              <option v-for="field in fields" :key="field.key" :value="field.key">{{ field.label || field.key }}</option>
            </select></label
          >
        </div>
        <div class="field">
          <label
            >So sánh<select v-model="step.condition.operator">
              <option value="eq">Bằng</option>
              <option value="ne">Khác</option>
              <option value="gt">Lớn hơn</option>
              <option value="gte">Lớn hơn hoặc bằng</option>
              <option value="lt">Nhỏ hơn</option>
              <option value="lte">Nhỏ hơn hoặc bằng</option>
            </select></label
          >
        </div>
        <div class="field full-width">
          <label
            >Giá trị<input
              v-model="step.condition.value"
              :type="fields.find((field) => field.key === step.condition?.field)?.type === 'number' ? 'number' : 'text'"
              required
          /></label>
        </div>
      </div>
    </div>
    <button
      type="button"
      class="button secondary small"
      style="justify-self: start"
      @click="steps.push({ label: '', resolver: 'user', user_id: '', due_hours: null })"
    >
      <Plus :size="15" />Thêm bước
    </button>
  </div>
</template>
