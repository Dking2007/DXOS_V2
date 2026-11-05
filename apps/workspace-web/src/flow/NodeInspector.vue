<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { computed } from 'vue'
import { Copy, Plus, Trash2 } from 'lucide-vue-next'
import { KINDS, OPERATORS, RECIPIENTS, RESOLVERS, waitLabel } from './nodes'
import type { FlowCondition, FlowNodeData, TriggerInfo } from './nodes'
const props = defineProps<{
  /** Drawing a dossier's process: the trigger picks a form instead of an event. */
  process?: boolean
  forms?: { id: string; name: string }[]
  data: FlowNodeData
  triggers: TriggerInfo[]
  /** Event fields available to conditions and text, from the flow's trigger. */
  fields: Record<string, string>
  users: { id: string; display_name: string }[]
  departments: { id: string; name: string }[]
  connections: { id: string; name: string; base_url: string }[]
  webhooksEnabled: boolean
}>()
const emit = defineEmits<{
  patch: [values: Record<string, unknown>]
  label: [value: string]
  remove: []
  duplicate: []
}>()
const c = computed(() => props.data.config)
const meta = computed(() => KINDS[props.data.kind])
const conditions = computed(() => (c.value.conditions as FlowCondition[]) ?? [])
function set(key: string, value: unknown) {
  emit('patch', { [key]: value })
}
function setCondition(index: number, key: keyof FlowCondition, value: unknown) {
  const next = conditions.value.map((item, i) => (i === index ? { ...item, [key]: value } : item))
  set('conditions', next)
}
/** Numbers, booleans and lists typed as JSON keep their type; anything else stays text. */
function parseValue(text: string): unknown {
  try {
    return JSON.parse(text)
  } catch {
    return text
  }
}
function showValue(value: unknown) {
  return typeof value === 'string' ? value : JSON.stringify(value ?? '')
}
function toggleRecipient(key: string) {
  const list = (c.value.recipients as string[]) ?? []
  set('recipients', list.includes(key) ? list.filter((r) => r !== key) : [...list, key])
}
function toggleUser(key: string, id: string) {
  const list = (c.value[key] as string[]) ?? []
  set(key, list.includes(id) ? list.filter((item) => item !== id) : [...list, id].slice(0, 10))
}
function setDays(event: Event) {
  const value = (event.target as HTMLInputElement).value
  set('due_in_days', value === '' ? null : Math.min(365, Math.max(0, Number(value))))
}
function insert(key: string, field: string) {
  const current = String(c.value[key] ?? '')
  set(key, `${current}${current && !current.endsWith(' ') ? ' ' : ''}{${field}}`)
}
const waitUnits = [
  { label: 'phút', factor: 1 },
  { label: 'giờ', factor: 60 },
  { label: 'ngày', factor: 1440 },
]
const waitUnit = computed(() => {
  const minutes = Number(c.value.minutes ?? 60)
  return [...waitUnits].reverse().find((unit) => minutes % unit.factor === 0) ?? waitUnits[0]
})
</script>
<template>
  <div class="inspector">
    <header class="inspector-head" :style="{ '--node-color': meta.color }">
      <span class="flow-node-icon small"><component :is="meta.icon" :size="18" /></span>
      <div class="grow">
        <small>{{ meta.group.toUpperCase() }}</small>
        <strong>{{ meta.title }}</strong>
      </div>
      <button
        v-if="data.kind !== 'trigger'"
        class="icon-button"
        title="Nhân bản"
        aria-label="Nhân bản node"
        @click="emit('duplicate')"
      >
        <Copy :size="16" /></button
      ><button
        v-if="data.kind !== 'trigger'"
        class="icon-button"
        title="Xóa node"
        aria-label="Xóa node"
        @click="emit('remove')"
      >
        <Trash2 :size="16" />
      </button>
    </header>
    <div v-if="data.errors?.length" class="notice error inspector-errors">
      <ul>
        <li v-for="message in data.errors" :key="message">{{ message }}</li>
      </ul>
    </div>
    <div class="inspector-body">
      <div class="field">
        <label for="node-label">Tên hiển thị</label
        ><input
          id="node-label"
          :value="data.label"
          :placeholder="meta.title"
          maxlength="120"
          @input="emit('label', ($event.target as HTMLInputElement).value)"
        />
      </div>

      <template v-if="data.kind === 'trigger' && process">
        <div class="field">
          <label for="node-form">Áp dụng cho biểu mẫu</label
          ><select
            id="node-form"
            :value="c.form_id ?? ''"
            @change="set('form_id', ($event.target as HTMLSelectElement).value || null)"
          >
            <option value="">Chọn biểu mẫu…</option>
            <option v-for="f in forms ?? []" :key="f.id" :value="f.id">{{ f.name }}</option>
          </select>
          <small>Quy trình chạy mỗi khi một hồ sơ của biểu mẫu này được trình (kể cả trình lại).</small>
        </div>
        <div class="field-help">
          <span class="section-label">Dữ liệu hồ sơ dùng được trong điều kiện và nội dung</span>
          <code v-for="(label, key) in fields" :key="key" class="var-chip" :title="label">{{ key }}</code>
        </div>
      </template>

      <template v-else-if="data.kind === 'approval'">
        <div class="field">
          <label for="node-resolver">Người duyệt</label
          ><select
            id="node-resolver"
            :value="c.resolver ?? 'department_manager'"
            @change="set('resolver', ($event.target as HTMLSelectElement).value)"
          >
            <option v-for="(label, key) in RESOLVERS" :key="key" :value="key">{{ label }}</option>
          </select>
        </div>
        <div v-if="c.resolver === 'user'" class="field">
          <label for="node-approver">Chọn người</label
          ><select
            id="node-approver"
            :value="c.user_id ?? ''"
            @change="set('user_id', ($event.target as HTMLSelectElement).value || null)"
          >
            <option value="">Chọn người duyệt…</option>
            <option v-for="u in users" :key="u.id" :value="u.id">{{ u.display_name }}</option>
          </select>
        </div>
        <div class="field">
          <label>Lựa chọn của người duyệt</label>
          <label class="checkbox-label"><input type="checkbox" checked disabled /> Duyệt</label>
          <label class="checkbox-label"
            ><input
              type="checkbox"
              :checked="c.allow_return !== false"
              @change="set('allow_return', ($event.target as HTMLInputElement).checked)"
            />
            Trả lại để bổ sung</label
          >
          <label class="checkbox-label"
            ><input
              type="checkbox"
              :checked="c.allow_reject !== false"
              @change="set('allow_reject', ($event.target as HTMLInputElement).checked)"
            />
            Từ chối</label
          >
          <small>Cổng nào không nối tiếp thì hồ sơ kết thúc theo đúng tên cổng (duyệt, cần bổ sung, bị từ chối).</small>
        </div>
        <div class="field">
          <label for="node-due-a">Hạn xử lý (ngày)</label
          ><input id="node-due-a" type="number" min="0" max="365" :value="c.due_in_days ?? ''" @change="setDays" />
        </div>
        <div class="field">
          <label for="node-instr">Hướng dẫn cho người duyệt</label
          ><textarea
            id="node-instr"
            rows="3"
            maxlength="1000"
            :value="String(c.instructions ?? '')"
            @change="set('instructions', ($event.target as HTMLTextAreaElement).value)"
          />
        </div>
        <p class="field-help muted">Người tạo hồ sơ không bao giờ tự duyệt hồ sơ của mình; khi đó bước báo lỗi cấu hình.</p>
      </template>

      <template v-else-if="data.kind === 'consult'">
        <div class="field">
          <label>Người cho ý kiến</label>
          <label class="checkbox-label"
            ><input
              type="checkbox"
              :checked="!!c.include_department_manager"
              @change="set('include_department_manager', ($event.target as HTMLInputElement).checked)"
            />
            Lãnh đạo đơn vị của hồ sơ</label
          >
          <select
            aria-label="Thêm người cho ý kiến"
            value=""
            @change="
              (event) => {
                const value = (event.target as HTMLSelectElement).value
                if (value) toggleUser('user_ids', value)
                ;(event.target as HTMLSelectElement).value = ''
              }
            "
          >
            <option value="">+ Thêm người…</option>
            <option v-for="u in users" :key="u.id" :value="u.id">{{ u.display_name }}</option>
          </select>
          <div class="chip-select">
            <button
              v-for="id in (c.user_ids as string[]) ?? []"
              :key="id"
              type="button"
              class="active"
              @click="toggleUser('user_ids', id)"
            >
              {{ users.find((u) => u.id === id)?.display_name ?? id.slice(0, 8) }} ✕
            </button>
          </div>
        </div>
        <div class="field">
          <label for="node-cmode">Đi cổng Đồng ý khi</label
          ><select id="node-cmode" :value="c.mode ?? 'all'" @change="set('mode', ($event.target as HTMLSelectElement).value)">
            <option value="all">Tất cả đã trả lời và đều đồng ý</option>
            <option value="any">Có một người đồng ý (không chờ người còn lại)</option>
          </select>
        </div>
        <div class="field">
          <label for="node-due-c">Hạn cho ý kiến (ngày)</label
          ><input id="node-due-c" type="number" min="0" max="365" :value="c.due_in_days ?? ''" @change="setDays" />
        </div>
        <div class="field">
          <label for="node-cinstr">Nội dung xin ý kiến</label
          ><textarea
            id="node-cinstr"
            rows="3"
            maxlength="1000"
            :value="String(c.instructions ?? '')"
            @change="set('instructions', ($event.target as HTMLTextAreaElement).value)"
          />
        </div>
      </template>

      <template v-else-if="data.kind === 'request_info'">
        <div class="field">
          <label for="node-req">Lời nhắn cho người tạo hồ sơ</label
          ><textarea
            id="node-req"
            rows="3"
            maxlength="1000"
            :value="String(c.message ?? '')"
            @change="set('message', ($event.target as HTMLTextAreaElement).value)"
          />
          <small>Hồ sơ chuyển sang “Cần bổ sung”; người tạo sửa rồi trình lại, quy trình chạy lại từ đầu.</small>
        </div>
      </template>

      <template v-else-if="data.kind === 'finish'">
        <div class="field">
          <label for="node-result">Kết quả hồ sơ</label
          ><select id="node-result" :value="c.result ?? 'approved'" @change="set('result', ($event.target as HTMLSelectElement).value)">
            <option value="approved">Được duyệt</option>
            <option value="rejected">Bị từ chối</option>
          </select>
        </div>
        <div class="field">
          <label for="node-fmsg">Lời nhắn kèm thông báo</label
          ><input
            id="node-fmsg"
            :value="String(c.message ?? '')"
            maxlength="1000"
            @change="set('message', ($event.target as HTMLInputElement).value)"
          />
        </div>
        <p class="field-help muted">Khi tới node này, các bước khác còn đang chờ được đóng lại.</p>
      </template>

      <template v-else-if="data.kind === 'trigger'">
        <div class="field">
          <label for="node-event">Sự kiện</label
          ><select id="node-event" :value="c.event" @change="set('event', ($event.target as HTMLSelectElement).value)">
            <option v-for="t in triggers" :key="t.key" :value="t.key">{{ t.label }}</option>
          </select>
        </div>
        <div class="field-help">
          <span class="section-label">Dữ liệu sự kiện mang theo</span>
          <code v-for="(label, key) in fields" :key="key" class="var-chip" :title="label">{{ key }}</code>
        </div>
      </template>

      <template v-else-if="data.kind === 'if'">
        <div class="field">
          <label for="node-mode">Đi nhánh Đúng khi</label
          ><select id="node-mode" :value="c.mode ?? 'all'" @change="set('mode', ($event.target as HTMLSelectElement).value)">
            <option value="all">Thỏa tất cả điều kiện</option>
            <option value="any">Thỏa ít nhất một điều kiện</option>
          </select>
        </div>
        <div v-for="(condition, index) in conditions" :key="index" class="condition-card">
          <div class="condition-row">
            <select
              :value="condition.field"
              aria-label="Trường dữ liệu"
              @change="setCondition(index, 'field', ($event.target as HTMLSelectElement).value)"
            >
              <option v-for="(label, key) in fields" :key="key" :value="key">{{ label }}</option>
              <option v-if="!(condition.field in fields)" :value="condition.field">{{ condition.field }}</option>
            </select>
            <select
              :value="condition.operator"
              aria-label="Phép so sánh"
              @change="setCondition(index, 'operator', ($event.target as HTMLSelectElement).value)"
            >
              <option v-for="(label, key) in OPERATORS" :key="key" :value="key">{{ label }}</option>
            </select>
          </div>
          <div class="condition-row">
            <input
              v-if="!['empty', 'not_empty'].includes(condition.operator)"
              :value="showValue(condition.value)"
              aria-label="Giá trị"
              placeholder="vd. urgent, 100, true"
              @change="setCondition(index, 'value', parseValue(($event.target as HTMLInputElement).value))"
            />
            <button
              class="icon-button"
              aria-label="Xóa điều kiện"
              @click="set('conditions', conditions.filter((_, i) => i !== index))"
            >
              <Trash2 :size="15" />
            </button>
          </div>
        </div>
        <button
          class="button ghost small"
          @click="set('conditions', [...conditions, { field: Object.keys(fields)[0] ?? 'title', operator: 'eq', value: '' }])"
        >
          <Plus :size="15" />Thêm điều kiện
        </button>
        <p class="field-help muted">
          Giá trị dạng số hoặc <code>true/false</code> được hiểu đúng kiểu; danh sách viết như
          <code>["a","b"]</code>.
        </p>
      </template>

      <template v-else-if="data.kind === 'ai'">
        <div class="field">
          <label for="node-ai-question">Câu hỏi cho AI</label>
          <textarea
            id="node-ai-question"
            rows="3"
            maxlength="500"
            :value="String(c.question ?? '')"
            @change="set('question', ($event.target as HTMLTextAreaElement).value)"
          />
          <small>AI đọc tiêu đề, trạng thái, mức ưu tiên, nhãn, nội dung của sự kiện rồi chọn đúng một đáp án.</small>
        </div>
        <div class="field">
          <label for="node-ai-choices">Các lựa chọn</label>
          <input
            id="node-ai-choices"
            :value="((c.choices as string[]) ?? []).join(', ')"
            placeholder="Gấp, Bình thường"
            @change="
              set(
                'choices',
                ($event.target as HTMLInputElement).value
                  .split(',')
                  .map((item) => item.trim())
                  .filter(Boolean)
                  .slice(0, 8),
              )
            "
          />
          <small>2 đến 8 lựa chọn, ngăn cách bằng dấu phẩy.</small>
        </div>
        <div class="field">
          <label for="node-ai-output">Lưu kết quả vào trường</label>
          <input
            id="node-ai-output"
            :value="String(c.output ?? 'ai_label')"
            pattern="[a-z_]{1,40}"
            @change="set('output', ($event.target as HTMLInputElement).value || 'ai_label')"
          />
          <small>Nối tiếp một node <strong>Điều kiện</strong> và chọn trường này để rẽ nhánh theo đáp án của AI.</small>
        </div>
      </template>

      <template v-else-if="data.kind === 'wait'">
        <div class="field">
          <label for="node-wait">Thời gian chờ</label>
          <div class="condition-row">
            <input
              id="node-wait"
              type="number"
              min="1"
              :value="Number(c.minutes ?? 60) / waitUnit.factor"
              @change="
                set('minutes', Math.max(1, Number(($event.target as HTMLInputElement).value)) * waitUnit.factor)
              "
            />
            <select
              :value="waitUnit.factor"
              aria-label="Đơn vị"
              @change="
                set(
                  'minutes',
                  (Number(c.minutes ?? 60) / waitUnit.factor) * Number(($event.target as HTMLSelectElement).value),
                )
              "
            >
              <option v-for="unit in waitUnits" :key="unit.factor" :value="unit.factor">{{ unit.label }}</option>
            </select>
          </div>
          <small>Tối đa 7 ngày. Hiện tại: {{ waitLabel(Number(c.minutes ?? 60)) }}.</small>
        </div>
      </template>

      <template v-else-if="data.kind === 'notify'">
        <div class="field">
          <label>Người nhận</label>
          <div class="chip-select">
            <button
              v-for="(label, key) in RECIPIENTS"
              :key="key"
              type="button"
              :class="{ active: ((c.recipients as string[]) ?? []).includes(key) }"
              @click="toggleRecipient(key)"
            >
              {{ label }}
            </button>
          </div>
          <select
            aria-label="Thêm người cụ thể"
            value=""
            @change="
              (event) => {
                const value = (event.target as HTMLSelectElement).value
                if (value) toggleRecipient(value)
                ;(event.target as HTMLSelectElement).value = ''
              }
            "
          >
            <option value="">+ Thêm người cụ thể…</option>
            <option v-for="u in users" :key="u.id" :value="u.id">{{ u.display_name }}</option>
          </select>
          <div class="chip-select">
            <button
              v-for="id in ((c.recipients as string[]) ?? []).filter((r) => !(r in RECIPIENTS))"
              :key="id"
              type="button"
              class="active"
              @click="toggleRecipient(id)"
            >
              {{ users.find((u) => u.id === id)?.display_name ?? id.slice(0, 8) }} ✕
            </button>
          </div>
        </div>
        <div class="field">
          <label for="node-title">Nội dung thông báo</label
          ><input id="node-title" :value="c.title" maxlength="250" @input="set('title', ($event.target as HTMLInputElement).value)" />
          <div class="var-row">
            <button v-for="(label, key) in fields" :key="key" type="button" class="var-chip" :title="label" @click="insert('title', String(key))">
              {{ '{' + key + '}' }}
            </button>
          </div>
        </div>
      </template>

      <template v-else-if="data.kind === 'create_task' || data.kind === 'assign_task'">
        <div class="field">
          <label for="node-ttitle">Tên việc</label
          ><input id="node-ttitle" :value="c.title" maxlength="250" @input="set('title', ($event.target as HTMLInputElement).value)" />
          <div class="var-row">
            <button v-for="(label, key) in fields" :key="key" type="button" class="var-chip" :title="label" @click="insert('title', String(key))">
              {{ '{' + key + '}' }}
            </button>
          </div>
        </div>
        <div class="field">
          <label for="node-tdesc">Mô tả</label
          ><textarea id="node-tdesc" rows="3" :value="String(c.description ?? '')" @input="set('description', ($event.target as HTMLTextAreaElement).value)" />
        </div>
        <div class="field">
          <label for="node-assignee">Giao cho</label
          ><select id="node-assignee" :value="c.assignee_id ?? ''" @change="set('assignee_id', ($event.target as HTMLSelectElement).value || null)">
            <option value="">— Theo đơn vị —</option>
            <option v-for="u in users" :key="u.id" :value="u.id">{{ u.display_name }}</option>
          </select>
        </div>
        <div class="field">
          <label for="node-dept">Đơn vị nhận</label
          ><select id="node-dept" :value="c.department_id ?? ''" @change="set('department_id', ($event.target as HTMLSelectElement).value || null)">
            <option value="">—</option>
            <option v-for="d in departments" :key="d.id" :value="d.id">{{ d.name }}</option>
          </select>
        </div>
        <div class="condition-row">
          <div class="field">
            <label for="node-due">Hạn sau (ngày)</label
            ><input
              id="node-due"
              type="number"
              min="0"
              max="365"
              :value="c.due_in_days ?? ''"
              @change="
                set('due_in_days', ($event.target as HTMLInputElement).value === '' ? null : Number(($event.target as HTMLInputElement).value))
              "
            />
          </div>
          <div class="field">
            <label for="node-prio">Ưu tiên</label
            ><select id="node-prio" :value="c.priority ?? 'normal'" @change="set('priority', ($event.target as HTMLSelectElement).value)">
              <option value="low">Thấp</option>
              <option value="normal">Bình thường</option>
              <option value="high">Cao</option>
              <option value="urgent">Khẩn</option>
            </select>
          </div>
        </div>
        <p class="field-help muted">
          Việc được tạo dưới danh nghĩa và trong quyền của người tạo luồng{{
            data.kind === 'assign_task' ? ', gắn với hồ sơ; quy trình chờ tới khi việc được nghiệm thu hoặc bị hủy' : ''
          }}.
        </p>
      </template>

      <template v-else-if="data.kind === 'webhook'">
        <div v-if="!webhooksEnabled" class="notice warning">
          Triển khai chưa cho phép gọi ra ngoài (<code>AUTOMATION_ALLOWED_HOSTS</code> đang trống).
        </div>
        <div class="field">
          <label for="node-conn">Kết nối</label
          ><select id="node-conn" :value="c.connection_id ?? ''" @change="set('connection_id', ($event.target as HTMLSelectElement).value || null)">
            <option value="">Chọn kết nối</option>
            <option v-for="conn in connections" :key="conn.id" :value="conn.id">{{ conn.name }}</option>
          </select>
          <small v-if="c.connection_id">{{ connections.find((x) => x.id === c.connection_id)?.base_url }}</small>
        </div>
        <div class="field">
          <label for="node-path">Đường dẫn</label
          ><input id="node-path" :value="c.path" placeholder="events" @input="set('path', ($event.target as HTMLInputElement).value)" />
        </div>
        <p class="field-help muted">
          Gửi POST kèm <code>Idempotency-Key</code>. Quá thời gian chờ thì ghi “chưa rõ kết quả” và không tự gửi lại.
        </p>
      </template>
    </div>
  </div>
</template>
