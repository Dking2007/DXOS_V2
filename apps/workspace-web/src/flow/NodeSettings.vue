<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { computed } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { Plus } from 'lucide-vue-next'
import type { Page } from '@dx/web-shared/api.ts'
import { api } from '../api'
import { OPERATORS, nodeReference } from './nodes'
import type { FlowCondition, NodeKind } from './nodes'
import { usePluginSteps } from './pluginNodes'

/** Settings of the logic, data and message steps, whose results later steps can read. */
const props = defineProps<{
  id: string
  kind: NodeKind
  config: Record<string, unknown>
  fields: Record<string, string>
  users: { id: string; display_name: string }[]
  connections: { id: string; name: string; base_url: string }[]
  forms: { id: string; name: string; fields?: Record<string, string> }[]
}>()
const emit = defineEmits<{ patch: [values: Record<string, unknown>] }>()
const c = computed(() => props.config)
const set = (key: string, value: unknown) => emit('patch', { [key]: value })
const text = (event: Event) => (event.target as HTMLInputElement).value
const checked = (event: Event) => (event.target as HTMLInputElement).checked
const list = <T,>(key: string) => (c.value[key] as T[] | undefined) ?? []
function setItem<T>(key: string, index: number, values: Partial<T>) {
  set(key, list<T>(key).map((item, i) => (i === index ? { ...item, ...values } : item)))
}
function removeItem(key: string, index: number) {
  set(key, list(key).filter((_, i) => i !== index))
}
const fieldEntries = computed(() => Object.entries(props.fields))
const reference = computed(() => nodeReference(props.id, props.config))
const pluginSteps = usePluginSteps()
const pluginStep = computed(() =>
  props.kind === 'plugin_action'
    ? (pluginSteps.data.value ?? []).find((step) => step.plugin_id === c.value.plugin_id && step.kind === c.value.node)
    : undefined,
)
const pluginConfig = computed(() => (c.value.config as Record<string, unknown>) ?? {})
/** How later steps write a value this step returns, e.g. "{tra_cuu.ten_dn}". */
function placeholder(key: string) {
  return '{' + reference.value + '.' + key + '}'
}
function setPluginValue(key: string, value: unknown) {
  set('config', { ...pluginConfig.value, [key]: value })
}
const conversations = useQuery({
  queryKey: ['conversations', 'flow-picker'],
  queryFn: () => api.request<Page<{ id: string; title: string; kind: string }>>('/conversations'),
  enabled: computed(() => props.kind === 'send_message' && c.value.channel !== 'feed'),
})
const folders = useQuery({
  queryKey: ['drive', 'folders', 'flow-picker'],
  queryFn: () => api.request<Page<{ id: string; name: string }>>('/drive/folders'),
  enabled: computed(() => props.kind === 'file_share' || props.kind === 'create_document'),
})
const caseForm = computed(() => props.forms.find((form) => form.id === c.value.form_id))
const caseFields = computed(() =>
  Object.entries(caseForm.value?.fields ?? {}).map(([key, label]) => ({ key: key.replace(/^form\./, ''), label })),
)
const answers = computed(() => (c.value.answers as Record<string, string>) ?? {})
const UPDATABLE = computed(() => [
  ['priority', 'Độ ưu tiên (low, normal, high, urgent)'],
  ['due_in_days', 'Hạn: số ngày kể từ bây giờ'],
  ...fieldEntries.value.filter(([key]) => key.startsWith('form.')),
])
const conditions = computed(() => list<FlowCondition>('conditions'))
const cases = computed(() => list<{ label: string; operator: string; value: unknown }>('cases'))
const changes = computed(() => list<{ field: string; value: string }>('changes'))
const extractFields = computed(() => list<{ key: string; label: string }>('fields'))
const userIds = computed(() => list<string>('user_ids'))
function toggleUser(id: string) {
  const current = list<string>('user_ids')
  set('user_ids', current.includes(id) ? current.filter((item) => item !== id) : [...current, id])
}
</script>
<template>
  <template v-if="kind === 'switch'">
    <div class="field">
      <label for="sw-field">Xét theo</label>
      <select id="sw-field" :value="c.field ?? ''" @change="set('field', text($event))">
        <option value="">Chọn trường…</option>
        <option v-for="[key, label] in fieldEntries" :key="key" :value="key">{{ label }}</option>
      </select>
    </div>
    <div v-for="(item, index) in cases" :key="index" class="condition-card">
      <input :value="item.label" :aria-label="`Tên nhánh ${index + 1}`" placeholder="Tên nhánh" @change="setItem('cases', index, { label: text($event) })" />
      <select :value="item.operator ?? 'eq'" :aria-label="`Phép so sánh ${index + 1}`" @change="setItem('cases', index, { operator: text($event) })">
        <option v-for="(label, key) in OPERATORS" :key="key" :value="key">{{ label }}</option>
      </select>
      <input :value="String(item.value ?? '')" :aria-label="`Giá trị ${index + 1}`" placeholder="Giá trị" @change="setItem('cases', index, { value: Number.isNaN(Number(text($event))) || text($event) === '' ? text($event) : Number(text($event)) })" />
      <button type="button" class="button ghost small" @click="removeItem('cases', index)">Xóa nhánh</button>
    </div>
    <button type="button" class="button secondary small" @click="set('cases', [...list('cases'), { label: `Nhánh ${list('cases').length + 1}`, operator: 'eq', value: '' }])">
      <Plus :size="14" />Thêm nhánh
    </button>
    <small class="muted">Đi nhánh đầu tiên thỏa; không nhánh nào thỏa thì đi cổng “Còn lại”.</small>
  </template>

  <p v-else-if="kind === 'parallel'" class="field-help muted">
    Mọi bước nối từ đây chạy cùng lúc. Dùng bước <b>Chờ đủ nhánh</b> để gom lại trước khi đi tiếp.
  </p>

  <div v-else-if="kind === 'join'" class="field">
    <label for="join-mode">Đi tiếp khi</label>
    <select id="join-mode" :value="c.mode ?? 'all'" @change="set('mode', text($event))">
      <option value="all">Đủ các nhánh còn có thể đến</option>
      <option value="any">Nhánh đầu tiên đến</option>
    </select>
    <small>Nhánh không còn đi được (ví dụ điều kiện rẽ sang hướng khác) thì không phải chờ.</small>
  </div>

  <template v-else-if="kind === 'wait_until'">
    <div class="field">
      <label for="wu-mode">Chờ</label>
      <select id="wu-mode" :value="c.mode ?? 'date'" @change="set('mode', text($event))">
        <option value="date">Đến một ngày trong dữ liệu</option>
        <option value="condition">Đến khi điều kiện đúng</option>
      </select>
    </div>
    <div v-if="(c.mode ?? 'date') === 'date'" class="field">
      <label for="wu-date">Trường chứa ngày</label>
      <select id="wu-date" :value="c.date_field ?? ''" @change="set('date_field', text($event))">
        <option value="">Chọn trường…</option>
        <option v-for="[key, label] in fieldEntries" :key="key" :value="key">{{ label }}</option>
      </select>
    </div>
    <template v-else>
      <div v-for="(item, index) in conditions" :key="index" class="condition-card">
        <select :value="item.field" :aria-label="`Trường ${index + 1}`" @change="setItem('conditions', index, { field: text($event) })">
          <option v-for="[key, label] in fieldEntries" :key="key" :value="key">{{ label }}</option>
        </select>
        <select :value="item.operator" :aria-label="`Phép so sánh ${index + 1}`" @change="setItem('conditions', index, { operator: text($event) })">
          <option v-for="(label, key) in OPERATORS" :key="key" :value="key">{{ label }}</option>
        </select>
        <input :value="String(item.value ?? '')" :aria-label="`Giá trị ${index + 1}`" @change="setItem('conditions', index, { value: text($event) })" />
        <button type="button" class="button ghost small" @click="removeItem('conditions', index)">Xóa</button>
      </div>
      <button type="button" class="button secondary small" @click="set('conditions', [...conditions, { field: fieldEntries[0]?.[0] ?? '', operator: 'eq', value: '' }])">
        <Plus :size="14" />Thêm điều kiện
      </button>
      <div class="field">
        <label for="wu-every">Kiểm tra lại sau (phút)</label>
        <input id="wu-every" type="number" min="5" max="1440" :value="c.check_every_minutes ?? 60" @change="set('check_every_minutes', Number(text($event)))" />
      </div>
      <div class="field">
        <label for="wu-timeout">Hết thời gian chờ sau (ngày)</label>
        <input id="wu-timeout" type="number" min="1" max="365" :value="c.timeout_days ?? ''" @change="set('timeout_days', text($event) ? Number(text($event)) : null)" />
        <small>Có giới hạn thì thêm cổng “Hết thời gian chờ”.</small>
      </div>
    </template>
  </template>

  <template v-else-if="kind === 'set_value'">
    <div class="field">
      <label for="sv-name">Tên giá trị</label>
      <input id="sv-name" :value="c.name ?? ''" placeholder="tong_tien" @change="set('name', text($event))" />
      <small>Chữ thường không dấu. Đọc ở bước sau: <code>{{ '{' + (c.name || 'ten') + '}' }}</code></small>
    </div>
    <div class="field">
      <label for="sv-value">Giá trị</label>
      <input id="sv-value" :value="c.value ?? ''" placeholder="{form.so_tien}" @change="set('value', text($event))" />
    </div>
    <div class="field">
      <label for="sv-op">Phép tính</label>
      <select id="sv-op" :value="c.operator ?? 'set'" @change="set('operator', text($event))">
        <option value="set">Giữ nguyên</option>
        <option value="add">Cộng</option>
        <option value="subtract">Trừ</option>
        <option value="multiply">Nhân</option>
        <option value="divide">Chia</option>
      </select>
    </div>
    <div v-if="(c.operator ?? 'set') !== 'set'" class="field">
      <label for="sv-operand">Với</label>
      <input id="sv-operand" :value="c.operand ?? ''" @change="set('operand', text($event))" />
    </div>
  </template>

  <template v-else-if="kind === 'update_record'">
    <p class="field-help muted">Cập nhật hồ sơ hoặc công việc mà luồng đang chạy trên đó.</p>
    <div v-for="(item, index) in changes" :key="index" class="condition-card">
      <select :value="item.field" :aria-label="`Trường cập nhật ${index + 1}`" @change="setItem('changes', index, { field: text($event) })">
        <option v-for="[key, label] in UPDATABLE" :key="key" :value="key">{{ label }}</option>
      </select>
      <input :value="item.value" :aria-label="`Giá trị mới ${index + 1}`" placeholder="Giá trị mới" @change="setItem('changes', index, { value: text($event) })" />
      <button type="button" class="button ghost small" @click="removeItem('changes', index)">Xóa</button>
    </div>
    <button type="button" class="button secondary small" @click="set('changes', [...list('changes'), { field: 'priority', value: '' }])">
      <Plus :size="14" />Thêm thay đổi
    </button>
  </template>

  <template v-else-if="kind === 'create_document'">
    <div class="field">
      <label for="doc-kind">Loại văn bản</label>
      <select id="doc-kind" :value="c.doc_kind ?? 'thong_bao'" @change="set('doc_kind', text($event))">
        <option value="thong_bao">Thông báo</option>
        <option value="to_trinh">Tờ trình</option>
        <option value="cong_van">Công văn</option>
        <option value="ke_hoach">Kế hoạch</option>
        <option value="bao_cao">Báo cáo</option>
      </select>
    </div>
    <div class="field">
      <label for="doc-agency">Tên cơ quan</label>
      <input id="doc-agency" :value="c.agency ?? ''" @change="set('agency', text($event))" />
    </div>
    <div class="field">
      <label for="doc-title">Tiêu đề</label>
      <input id="doc-title" :value="c.title ?? ''" @change="set('title', text($event))" />
    </div>
    <div class="field">
      <label for="doc-body">Nội dung</label>
      <textarea id="doc-body" rows="6" :value="String(c.body ?? '')" @change="set('body', text($event))" />
      <small>Dùng được dữ liệu như <code>{title}</code>, <code>{form.so_tien}</code>. Mỗi dòng là một đoạn.</small>
    </div>
    <label class="checkbox-label"><input type="checkbox" :checked="c.attach !== false" @change="set('attach', checked($event))" /> Đính kèm vào hồ sơ</label>
  </template>

  <template v-else-if="kind === 'file_share'">
    <div class="field">
      <label for="fs-file">Tệp</label>
      <input id="fs-file" :value="c.file_id ?? ''" placeholder="{tao_van_ban.file_id}" @change="set('file_id', text($event))" />
      <small>Thường là kết quả của một bước trước. Người tạo luồng phải là chủ tệp.</small>
    </div>
    <div class="field">
      <label for="fs-folder">Chuyển vào thư mục</label>
      <select id="fs-folder" :value="c.folder_id ?? ''" @change="set('folder_id', text($event) || null)">
        <option value="">Giữ nguyên</option>
        <option v-for="item in folders.data.value?.items" :key="item.id" :value="item.id">{{ item.name }}</option>
      </select>
    </div>
    <div class="field">
      <label for="fs-user">Cho xem</label>
      <select id="fs-user" value="" @change="(event) => { if (text(event)) toggleUser(text(event)); (event.target as HTMLSelectElement).value = '' }">
        <option value="">+ Thêm người…</option>
        <option v-for="u in users" :key="u.id" :value="u.id">{{ u.display_name }}</option>
      </select>
      <div class="chip-select">
        <button v-for="userId in userIds" :key="userId" type="button" class="active" @click="toggleUser(userId)">
          {{ users.find((u) => u.id === userId)?.display_name ?? userId.slice(0, 8) }} ✕
        </button>
      </div>
    </div>
  </template>

  <template v-else-if="kind === 'create_case'">
    <div class="field">
      <label for="cc-form">Biểu mẫu của hồ sơ mới</label>
      <select id="cc-form" :value="c.form_id ?? ''" @change="set('form_id', text($event) || null)">
        <option value="">Chọn biểu mẫu…</option>
        <option v-for="form in forms" :key="form.id" :value="form.id">{{ form.name }}</option>
      </select>
      <small>Hồ sơ được tạo ở dạng bản nháp để chủ hồ sơ kiểm tra rồi tự trình.</small>
    </div>
    <div class="field">
      <label for="cc-title">Tên hồ sơ</label>
      <input id="cc-title" :value="c.title ?? ''" @change="set('title', text($event))" />
    </div>
    <div v-for="field in caseFields" :key="field.key" class="field">
      <label :for="`cc-${field.key}`">{{ field.label }}</label>
      <input :id="`cc-${field.key}`" :value="answers[field.key] ?? ''" @change="set('answers', { ...answers, [field.key]: text($event) })" />
    </div>
  </template>

  <template v-else-if="kind === 'send_message'">
    <div class="field">
      <label for="msg-channel">Gửi tới</label>
      <select id="msg-channel" :value="c.channel ?? 'chat'" @change="set('channel', text($event))">
        <option value="chat">Một hội thoại</option>
        <option value="feed">Bảng tin</option>
      </select>
    </div>
    <div v-if="(c.channel ?? 'chat') === 'chat'" class="field">
      <label for="msg-room">Hội thoại</label>
      <select id="msg-room" :value="c.conversation_id ?? ''" @change="set('conversation_id', text($event) || null)">
        <option value="">Chọn hội thoại…</option>
        <option v-for="room in conversations.data.value?.items" :key="room.id" :value="room.id">{{ room.title || 'Hội thoại' }}</option>
      </select>
      <small>Chỉ gửi được vào hội thoại mà người tạo luồng đang tham gia.</small>
    </div>
    <div v-else class="field">
      <label for="msg-audience">Hiển thị cho</label>
      <select id="msg-audience" :value="c.audience ?? 'organization'" @change="set('audience', text($event))">
        <option value="organization">Toàn tổ chức</option>
        <option value="department">Phòng ban của người tạo luồng</option>
      </select>
    </div>
    <div class="field">
      <label for="msg-body">Nội dung</label>
      <textarea id="msg-body" rows="4" :value="String(c.body ?? '')" @change="set('body', text($event))" />
    </div>
  </template>

  <template v-else-if="kind === 'send_email'">
    <div class="field">
      <label for="mail-to">Người nhận</label>
      <input id="mail-to" :value="c.to ?? ''" placeholder="ke-toan@cong-ty.vn, {form.email}" @change="set('to', text($event))" />
    </div>
    <div class="field">
      <label for="mail-subject">Tiêu đề</label>
      <input id="mail-subject" :value="c.subject ?? ''" @change="set('subject', text($event))" />
    </div>
    <div class="field">
      <label for="mail-body">Nội dung</label>
      <textarea id="mail-body" rows="5" :value="String(c.body ?? '')" @change="set('body', text($event))" />
      <small>Cần cấu hình máy chủ thư (<code>SMTP_HOST</code>) khi triển khai.</small>
    </div>
  </template>

  <template v-else-if="kind === 'http_request'">
    <div class="field">
      <label for="http-conn">Kết nối</label>
      <select id="http-conn" :value="c.connection_id ?? ''" @change="set('connection_id', text($event) || null)">
        <option value="">Chọn kết nối…</option>
        <option v-for="item in connections" :key="item.id" :value="item.id">{{ item.name }}</option>
      </select>
    </div>
    <div class="field">
      <label for="http-method">Phương thức</label>
      <select id="http-method" :value="c.method ?? 'GET'" @change="set('method', text($event))">
        <option value="GET">GET: chỉ đọc dữ liệu</option>
        <option value="POST">POST: gửi dữ liệu luồng</option>
      </select>
    </div>
    <div class="field">
      <label for="http-path">Đường dẫn</label>
      <input id="http-path" :value="c.path ?? ''" placeholder="/ton-kho/{form.ma_hang}" @change="set('path', text($event))" />
      <small>Đọc giá trị trả về ở bước sau: <code>{{ `{${reference}.ten_truong}` }}</code>. Chỉ lấy giá trị đơn, không lấy dữ liệu lồng nhau.</small>
    </div>
  </template>

  <template v-else-if="kind === 'plugin_action'">
    <p v-if="pluginSteps.isPending.value" class="muted">Đang tải bước của plugin…</p>
    <div v-else-if="!pluginStep" class="notice warning">
      Plugin của bước này đang tắt, chưa được duyệt hoặc đã bị gỡ. Luồng sẽ không chạy được bước này.
    </div>
    <template v-else>
      <p class="muted">
        <strong>{{ pluginStep.plugin_name }}</strong> · {{ pluginStep.description || pluginStep.title }}
      </p>
      <div v-for="(field, key) in pluginStep.config_schema.properties" :key="key" class="field">
        <label v-if="field.type !== 'boolean'" :for="`plugin-${key}`"
          >{{ field.title
          }}<span v-if="pluginStep.config_schema.required.includes(String(key))" class="required"> *</span></label
        >
        <select
          v-if="field.enum?.length"
          :id="`plugin-${key}`"
          :value="pluginConfig[key] ?? ''"
          @change="setPluginValue(String(key), text($event))"
        >
          <option value="">Chọn…</option>
          <option v-for="option in field.enum" :key="option" :value="option">{{ option }}</option>
        </select>
        <label v-else-if="field.type === 'boolean'" class="checkbox-label"
          ><input
            type="checkbox"
            :checked="pluginConfig[key] === true"
            @change="setPluginValue(String(key), checked($event))"
          />{{ field.title }}</label
        >
        <input
          v-else
          :id="`plugin-${key}`"
          :value="pluginConfig[key] ?? ''"
          :placeholder="field.type === 'number' ? 'Số, hoặc {form.truong}' : 'Chữ, có thể chèn {form.truong}'"
          @change="
            setPluginValue(
              String(key),
              field.type === 'number' && /^-?\d+(\.\d+)?$/.test(text($event)) ? Number(text($event)) : text($event),
            )
          "
        />
        <small v-if="field.description">{{ field.description }}</small>
      </div>
      <label class="checkbox-label"
        ><input type="checkbox" :checked="c.send_files === true" @change="set('send_files', checked($event))" /> Gửi
        danh sách tài liệu của hồ sơ (chỉ mã và tên, không gửi nội dung)</label
      >
      <small class="muted"
        >Chỉ các ô trên (đã điền giá trị) được gửi cho plugin, có chữ ký. Bước sau đọc kết quả:
        <code v-for="(label, key) in pluginStep.outputs" :key="key" :title="label">{{ placeholder(String(key)) }} </code></small
      >
    </template>
  </template>

  <template v-else-if="kind === 'ai_extract'">
    <label class="checkbox-label"><input type="checkbox" :checked="c.read_files !== false" @change="set('read_files', checked($event))" /> Đọc tài liệu đính kèm của hồ sơ</label>
    <div class="field">
      <label for="ai-text">Nội dung thêm</label>
      <textarea id="ai-text" rows="3" :value="String(c.text ?? '')" @change="set('text', text($event))" />
    </div>
    <span class="section-label">Các trường cần lấy</span>
    <div v-for="(item, index) in extractFields" :key="index" class="condition-card">
      <input :value="item.key" :aria-label="`Mã trường ${index + 1}`" placeholder="so_tien" @change="setItem('fields', index, { key: text($event) })" />
      <input :value="item.label" :aria-label="`Mô tả trường ${index + 1}`" placeholder="Số tiền đề nghị" @change="setItem('fields', index, { label: text($event) })" />
      <button type="button" class="button ghost small" @click="removeItem('fields', index)">Xóa</button>
    </div>
    <button type="button" class="button secondary small" @click="set('fields', [...list('fields'), { key: '', label: '' }])">
      <Plus :size="14" />Thêm trường
    </button>
    <small class="muted">Luôn có thêm bản tóm tắt: <code>{{ `{${reference}.summary}` }}</code>. Cần bật tính năng “Hỏi AI trong luồng”.</small>
  </template>
</template>
