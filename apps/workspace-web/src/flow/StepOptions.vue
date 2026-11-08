<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { computed } from 'vue'
import { roleLabel } from '../ui/labels'
import FieldListEditor, { type StepField } from './FieldListEditor.vue'
import { nodeReference } from './nodes'

/** What every step that waits for people has: who is asked, how many, by when, what they see. */
const props = defineProps<{
  kind: 'approval' | 'consult' | 'input' | 'acknowledge'
  nodeId: string
  config: Record<string, unknown>
  users: { id: string; display_name: string }[]
  departments: { id: string; name: string }[]
  /** Form fields as the flow knows them: `form.<key>` to label. */
  fields: Record<string, string>
}>()
const emit = defineEmits<{ patch: [values: Record<string, unknown>] }>()
const c = computed(() => props.config)
const defaults = { approval: 'department_manager', consult: 'users', input: 'owner', acknowledge: 'users' } as const
const reference = computed(() => nodeReference(props.nodeId, c.value))
const resultFields = computed(() => (c.value.result_fields as StepField[]) ?? [])
const resolver = computed(() => String(c.value.resolver ?? defaults[props.kind]))
const RESOLVER_OPTIONS = computed(() => [
  ...(props.kind === 'input' || props.kind === 'acknowledge' ? [['owner', 'Người tạo hồ sơ']] : []),
  ['department_manager', 'Lãnh đạo đơn vị của hồ sơ'],
  ['user', 'Một người cụ thể'],
  ['users', 'Một nhóm người'],
  ['role', 'Theo vai trò'],
  ['department', 'Thành viên một phòng ban'],
  ['form_field', 'Người ghi trong biểu mẫu'],
])
const ROLES = ['staff', 'manager', 'director', 'technical_admin']
const formFields = computed(() =>
  Object.entries(props.fields)
    .filter(([key]) => key.startsWith('form.'))
    .map(([key, label]) => ({ key: key.slice(5), label })),
)
const overdue = computed(() => (c.value.overdue ?? { action: 'none' }) as { action: string; user_id?: string | null })
const groupAsked = computed(() => ['users', 'role', 'department'].includes(resolver.value))
const limited = computed(() => Array.isArray(c.value.visible_fields))
const visible = computed(() => (c.value.visible_fields as string[] | null) ?? [])
const editable = computed(() => (c.value.editable_fields as string[]) ?? [])

function set(key: string, value: unknown) {
  emit('patch', { [key]: value })
}
const value = (event: Event) => (event.target as HTMLSelectElement).value
const checked = (event: Event) => (event.target as HTMLInputElement).checked
function setDays(event: Event) {
  const text = value(event)
  set('due_in_days', text === '' ? null : Math.min(365, Math.max(0, Number(text))))
}
function toggle(key: 'user_ids', id: string) {
  const list = (c.value[key] as string[]) ?? []
  set(key, list.includes(id) ? list.filter((item) => item !== id) : [...list, id].slice(0, 30))
}
function setLimited(on: boolean) {
  emit('patch', {
    visible_fields: on ? formFields.value.map((field) => field.key) : null,
  })
}
function toggleField(key: string) {
  const next = visible.value.includes(key) ? visible.value.filter((item) => item !== key) : [...visible.value, key]
  emit('patch', { visible_fields: next, editable_fields: editable.value.filter((item) => next.includes(item)) })
}
function toggleEditable(key: string) {
  set('editable_fields', editable.value.includes(key) ? editable.value.filter((item) => item !== key) : [...editable.value, key])
}
</script>
<template>
  <div class="field">
    <label for="step-resolver">Người xử lý</label>
    <select id="step-resolver" :value="resolver" @change="set('resolver', value($event))">
      <option v-for="[key, label] in RESOLVER_OPTIONS" :key="key" :value="key">{{ label }}</option>
    </select>
  </div>
  <div v-if="resolver === 'user'" class="field">
    <label for="step-user">Chọn người</label>
    <select id="step-user" :value="c.user_id ?? ''" @change="set('user_id', value($event) || null)">
      <option value="">Chọn người…</option>
      <option v-for="u in users" :key="u.id" :value="u.id">{{ u.display_name }}</option>
    </select>
  </div>
  <div v-if="resolver === 'users'" class="field">
    <label for="step-users">Những người được hỏi</label>
    <select
      id="step-users"
      value=""
      @change="
        (event) => {
          if (value(event)) toggle('user_ids', value(event))
          ;(event.target as HTMLSelectElement).value = ''
        }
      "
    >
      <option value="">+ Thêm người…</option>
      <option v-for="u in users" :key="u.id" :value="u.id">{{ u.display_name }}</option>
    </select>
    <div class="chip-select">
      <button v-for="id in (c.user_ids as string[]) ?? []" :key="id" type="button" class="active" @click="toggle('user_ids', id)">
        {{ users.find((u) => u.id === id)?.display_name ?? id.slice(0, 8) }} ✕
      </button>
    </div>
  </div>
  <template v-if="resolver === 'role'">
    <div class="field">
      <label for="step-role">Vai trò</label>
      <select id="step-role" :value="c.role ?? ''" @change="set('role', value($event) || null)">
        <option value="">Chọn vai trò…</option>
        <option v-for="role in ROLES" :key="role" :value="role">{{ roleLabel(role) }}</option>
      </select>
    </div>
    <div class="field">
      <label for="step-scope">Trong phạm vi</label>
      <select id="step-scope" :value="c.role_scope ?? 'department'" @change="set('role_scope', value($event))">
        <option value="department">Đơn vị của hồ sơ</option>
        <option value="organization">Toàn tổ chức</option>
      </select>
    </div>
  </template>
  <div v-if="resolver === 'department'" class="field">
    <label for="step-department">Phòng ban</label>
    <select id="step-department" :value="c.department_id ?? ''" @change="set('department_id', value($event) || null)">
      <option value="">Đơn vị của hồ sơ</option>
      <option v-for="d in departments" :key="d.id" :value="d.id">{{ d.name }}</option>
    </select>
  </div>
  <div v-if="resolver === 'form_field'" class="field">
    <label for="step-field">Trường ghi người xử lý</label>
    <select id="step-field" :value="c.form_field ?? ''" @change="set('form_field', value($event) || null)">
      <option value="">Chọn trường…</option>
      <option v-for="field in formFields" :key="field.key" :value="field.key">{{ field.label }}</option>
    </select>
    <small>Trường cần ghi đúng họ tên trong hệ thống. Tên trùng hoặc không khớp thì quy trình dừng và báo lỗi.</small>
  </div>
  <label v-if="kind === 'consult'" class="checkbox-label">
    <input type="checkbox" :checked="!!c.include_department_manager" @change="set('include_department_manager', checked($event))" />
    Thêm lãnh đạo đơn vị của hồ sơ
  </label>

  <div v-if="kind === 'approval' && groupAsked" class="field">
    <label for="step-mode">Bước hoàn tất khi</label>
    <select id="step-mode" :value="c.mode ?? 'any'" @change="set('mode', value($event))">
      <option value="any">Người đầu tiên trả lời</option>
      <option value="all">Tất cả phải duyệt</option>
      <option value="quorum">Đủ số người duyệt</option>
    </select>
    <small>Khi cần nhiều người, một người trả lại là hồ sơ đi cổng Trả lại ngay.</small>
  </div>
  <div v-if="kind === 'consult'" class="field">
    <label for="step-cmode">Đi cổng Đồng ý khi</label>
    <select id="step-cmode" :value="c.mode ?? 'all'" @change="set('mode', value($event))">
      <option value="all">Tất cả đã trả lời và đều đồng ý</option>
      <option value="any">Có một người đồng ý (không chờ người còn lại)</option>
      <option value="quorum">Đủ số người đồng ý</option>
    </select>
  </div>
  <div v-if="c.mode === 'quorum'" class="field">
    <label for="step-quorum">Số người cần đồng ý</label>
    <input id="step-quorum" type="number" min="1" max="30" :value="c.quorum ?? ''" @change="set('quorum', Number(value($event)) || null)" />
  </div>

  <div class="field">
    <label for="step-due">Hạn xử lý (ngày)</label>
    <input id="step-due" type="number" min="0" max="365" :value="c.due_in_days ?? ''" @change="setDays" />
  </div>
  <div class="field">
    <label for="step-overdue">Khi quá hạn</label>
    <select
      id="step-overdue"
      :value="overdue.action"
      :disabled="c.due_in_days == null"
      @change="set('overdue', { ...overdue, action: value($event) })"
    >
      <option value="none">Không làm gì</option>
      <option value="remind">Nhắc người đang xử lý</option>
      <option value="escalate">Chuyển cho người khác</option>
      <option value="branch">Đi theo cổng Quá hạn</option>
    </select>
    <small v-if="c.due_in_days == null">Đặt hạn xử lý để chọn.</small>
  </div>
  <div v-if="overdue.action === 'escalate'" class="field">
    <label for="step-escalate">Chuyển cho</label>
    <select id="step-escalate" :value="overdue.user_id ?? ''" @change="set('overdue', { ...overdue, user_id: value($event) || null })">
      <option value="">Lãnh đạo đơn vị của hồ sơ</option>
      <option v-for="u in users" :key="u.id" :value="u.id">{{ u.display_name }}</option>
    </select>
  </div>

  <div class="field">
    <label for="step-output">Tên kết quả của bước</label>
    <input id="step-output" :value="c.output_name ?? ''" :placeholder="reference" @change="set('output_name', value($event) || null)" />
    <small>Bước sau đọc kết quả bằng tên này, ví dụ <code>{{ `{${reference}.decision}` }}</code>.</small>
  </div>
  <template v-if="kind === 'approval' || kind === 'consult'">
    <div class="field">
      <label>Phải nộp khi đồng ý</label>
      <FieldListEditor :fields="resultFields" :reference="reference" @update="set('result_fields', $event)" />
    </div>
  </template>
  <div v-if="kind !== 'acknowledge'" class="field">
    <label for="step-files">Số tệp phải nộp</label>
    <input id="step-files" type="number" min="0" max="30" :value="c.require_files ?? 0" @change="set('require_files', Number(value($event)))" />
    <small>Trả lại hoặc từ chối thì không phải nộp.</small>
  </div>

  <div class="field">
    <label>Người ở bước này được xem</label>
    <label class="checkbox-label">
      <input type="checkbox" :checked="limited" @change="setLimited(checked($event))" /> Chỉ một số trường của biểu mẫu
    </label>
    <div v-if="limited" class="stack" style="padding-left: 22px">
      <label v-for="field in formFields" :key="field.key" class="checkbox-label">
        <input type="checkbox" :checked="visible.includes(field.key)" @change="toggleField(field.key)" /> {{ field.label }}
      </label>
    </div>
    <label class="checkbox-label">
      <input type="checkbox" :checked="!!c.hide_files" @change="set('hide_files', checked($event))" /> Không xem tài liệu đính kèm
    </label>
    <small>Không áp dụng với người tạo hồ sơ và người vốn được xem hồ sơ theo vai trò, như lãnh đạo đơn vị.</small>
  </div>
  <div v-if="kind !== 'input' && kind !== 'acknowledge' && formFields.length" class="field">
    <label>Được sửa khi trả lời</label>
    <label
      v-for="field in formFields.filter((item) => !limited || visible.includes(item.key))"
      :key="field.key"
      class="checkbox-label"
    >
      <input type="checkbox" :checked="editable.includes(field.key)" @change="toggleEditable(field.key)" /> {{ field.label }}
    </label>
  </div>
  <div class="field">
    <label>Chuyển người xử lý</label>
    <label class="checkbox-label">
      <input type="checkbox" :checked="c.allow_delegation !== false" @change="set('allow_delegation', checked($event))" />
      Người được ủy quyền được xử lý thay
    </label>
    <label class="checkbox-label">
      <input type="checkbox" :checked="!!c.allow_forward" @change="set('allow_forward', checked($event))" />
      Người được hỏi được chuyển cho người khác
    </label>
  </div>
</template>
