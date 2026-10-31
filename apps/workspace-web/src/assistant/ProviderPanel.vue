<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { computed, ref } from 'vue'
import { CheckCircle2, KeyRound, Pencil, Plug, Plus, Star, Trash2, XCircle } from 'lucide-vue-next'
import type { AssistantAdmin, AssistantProvider } from '@dx/web-shared/types.ts'
import { errorText, formatDate } from '@dx/web-shared/api.ts'
import ModalDialog from '@dx/web-shared/components/ModalDialog.vue'
import StatePanel from '@dx/web-shared/components/StatePanel.vue'
import { api } from '../api'
import { toast } from '../ui/toast'
import { confirmDiscard } from '../ui/unsaved'
import { GATEWAY_ICONS, GATEWAY_PROTOCOLS, gatewayEndpoint, PROVIDER_LOGOS } from './logos'

const props = defineProps<{ providers: AssistantProvider[]; kinds: AssistantAdmin['kinds'] }>()
const emit = defineEmits<{ changed: [] }>()

const KIND_HINTS: Record<string, string> = {
  anthropic: 'Lấy khóa tại console.anthropic.com › API Keys.',
  openai: 'Lấy khóa tại platform.openai.com › API keys.',
  gemini: 'Lấy khóa tại aistudio.google.com › Get API key.',
  deepseek: 'Lấy khóa tại platform.deepseek.com › API keys.',
  custom_anthropic: 'Khóa do cổng cấp, gửi trong header x-api-key.',
  custom_chat: 'Khóa do cổng cấp, gửi trong header Authorization: Bearer.',
  custom_responses: 'Khóa do cổng cấp, gửi trong header Authorization: Bearer.',
}
const official = computed(() => props.kinds.filter((k) => !k.custom))
const gateways = computed(() => props.kinds.filter((k) => k.custom))
const isGateway = computed(() => !!GATEWAY_PROTOCOLS[kind.value])
const dialog = ref<'add' | 'edit' | null>(null)
const editing = ref<AssistantProvider | null>(null)
const kind = ref<AssistantProvider['kind']>('anthropic')
const name = ref('')
const model = ref('')
const apiKey = ref('')
const baseUrl = ref('')
const maxTokens = ref(4000)
const error = ref('')
const busy = ref(false)
const testing = ref('')
const opened = ref('')
const state = () => JSON.stringify([kind.value, name.value, model.value, apiKey.value, maxTokens.value, baseUrl.value])
const preview = computed(() => gatewayEndpoint(kind.value, baseUrl.value || editing.value?.base_url || ''))

function openAdd() {
  dialog.value = 'add'
  editing.value = null
  kind.value = 'anthropic'
  pickKind('anthropic')
  apiKey.value = ''
  baseUrl.value = ''
  maxTokens.value = 4000
  error.value = ''
  opened.value = state()
}
function openEdit(item: AssistantProvider) {
  dialog.value = 'edit'
  editing.value = item
  kind.value = item.kind
  name.value = item.name
  model.value = item.model
  apiKey.value = ''
  baseUrl.value = ''
  maxTokens.value = item.max_output_tokens
  error.value = ''
  opened.value = state()
}
function pickKind(value: AssistantProvider['kind']) {
  kind.value = value
  const info = props.kinds.find((k) => k.kind === value)
  name.value = info?.label ?? ''
  model.value = info?.suggested_model ?? ''
}
function close() {
  if (!busy.value && confirmDiscard(state() !== opened.value)) dialog.value = null
}
const canSave = computed(
  () =>
    !!name.value.trim() &&
    !!model.value.trim() &&
    (dialog.value === 'edit' || apiKey.value.trim().length >= 8) &&
    (!isGateway.value || dialog.value === 'edit' || !!preview.value),
)
async function save() {
  busy.value = true
  error.value = ''
  try {
    if (dialog.value === 'add')
      await api.request('/assistant/providers', {
        method: 'POST',
        body: JSON.stringify({
          name: name.value,
          kind: kind.value,
          model: model.value,
          api_key: apiKey.value,
          max_output_tokens: Number(maxTokens.value),
          base_url: baseUrl.value,
        }),
      })
    else if (editing.value)
      await api.request(`/assistant/providers/${editing.value.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          expected_revision: editing.value.revision,
          name: name.value,
          model: model.value,
          api_key: apiKey.value,
          max_output_tokens: Number(maxTokens.value),
          base_url: baseUrl.value,
        }),
      })
    toast.success(dialog.value === 'add' ? 'Đã thêm dịch vụ AI. Bấm “Kiểm tra” để thử kết nối.' : 'Đã lưu dịch vụ AI')
    dialog.value = null
    emit('changed')
  } catch (cause) {
    error.value = errorText(cause)
  } finally {
    busy.value = false
  }
}
async function test(item: AssistantProvider) {
  testing.value = item.id
  try {
    const result = await api.request<{ ok: boolean; message: string }>(`/assistant/providers/${item.id}/test`, {
      method: 'POST',
    })
    if (result.ok) toast.success(`Kết nối được. Dịch vụ trả lời: “${result.message}”`)
    else toast.error(`Không kết nối được: ${result.message}`)
    emit('changed')
  } catch (cause) {
    toast.error(cause)
  } finally {
    testing.value = ''
  }
}
async function activate(item: AssistantProvider) {
  try {
    await api.request(`/assistant/providers/${item.id}/activate`, { method: 'POST' })
    toast.success(`Trợ lý giờ dùng “${item.name}”`)
    emit('changed')
  } catch (cause) {
    toast.error(cause)
  }
}
async function remove(item: AssistantProvider) {
  const warning = item.active ? ' Đây là dịch vụ đang dùng: trợ lý sẽ ngừng trả lời cho tới khi chọn dịch vụ khác.' : ''
  if (!window.confirm(`Xóa dịch vụ “${item.name}” và khóa API đã lưu?${warning}`)) return
  try {
    await api.request(`/assistant/providers/${item.id}`, { method: 'DELETE' })
    toast.success('Đã xóa dịch vụ AI')
    emit('changed')
  } catch (cause) {
    toast.error(cause)
  }
}
</script>
<template>
  <section class="card">
    <header class="card-header">
      <div>
        <h2>Dịch vụ AI</h2>
        <p class="muted" style="font-size: 14px; margin-top: 4px">
          Trợ lý dùng dịch vụ được đánh dấu <strong>Đang dùng</strong>. Khóa API được mã hóa và không bao giờ hiển
          thị lại.
        </p>
      </div>
      <button class="button" type="button" @click="openAdd"><Plus :size="16" />Thêm dịch vụ</button>
    </header>
    <StatePanel
      v-if="!providers.length"
      empty
      compact
      title="Chưa có dịch vụ AI nào"
      description="Thêm Claude, OpenAI, Gemini hoặc DeepSeek bằng khóa API của cơ quan."
      ><button class="button small" type="button" @click="openAdd"><Plus :size="15" />Thêm dịch vụ</button></StatePanel
    >
    <div class="provider-list">
      <article v-for="item in providers" :key="item.id" class="provider-card" :class="{ active: item.active }">
        <span class="provider-logo" :class="{ gateway: GATEWAY_ICONS[item.kind] }" aria-hidden="true"
          ><img v-if="PROVIDER_LOGOS[item.kind]" :src="PROVIDER_LOGOS[item.kind]" alt="" /><component
            :is="GATEWAY_ICONS[item.kind]"
            v-else
            :size="22"
        /></span>
        <div class="grow">
          <strong>{{ item.name }}</strong>
          <small>{{ item.kind_label }} · model <code>{{ item.model }}</code></small>
          <small v-if="item.endpoint" class="provider-endpoint"><code>{{ item.endpoint }}</code></small>
          <small
            ><KeyRound :size="12" /> Khóa {{ item.key_hint }} ·
            <template v-if="item.last_test_ok === true"
              ><CheckCircle2 :size="12" class="ok" /> Kết nối tốt {{ formatDate(item.last_test_at, true) }}</template
            ><template v-else-if="item.last_test_ok === false"
              ><XCircle :size="12" class="bad" /> Lần kiểm tra gần nhất lỗi</template
            ><template v-else>Chưa kiểm tra</template></small
          >
        </div>
        <span v-if="item.active" class="provider-active"><Star :size="13" />Đang dùng</span>
        <div class="provider-actions">
          <button class="button secondary small" type="button" :disabled="!!testing" @click="test(item)">
            <Plug :size="14" />{{ testing === item.id ? 'Đang kiểm tra…' : 'Kiểm tra' }}
          </button>
          <button v-if="!item.active" class="button secondary small" type="button" @click="activate(item)">
            Dùng dịch vụ này
          </button>
          <button class="icon-button" type="button" :aria-label="`Sửa ${item.name}`" title="Sửa" @click="openEdit(item)">
            <Pencil :size="16" />
          </button>
          <button class="icon-button" type="button" :aria-label="`Xóa ${item.name}`" title="Xóa" @click="remove(item)">
            <Trash2 :size="16" />
          </button>
        </div>
      </article>
    </div>
  </section>
  <ModalDialog v-if="dialog" :title="dialog === 'add' ? 'Thêm dịch vụ AI' : 'Sửa dịch vụ AI'" @close="close">
    <form class="stack" @submit.prevent="save">
      <div v-if="error" class="notice error" role="alert">{{ error }}</div>
      <template v-if="dialog === 'add'">
        <span class="section-label">Dịch vụ chính hãng</span>
        <div class="kind-picker" role="radiogroup" aria-label="Dịch vụ chính hãng">
          <button
            v-for="item in official"
            :key="item.kind"
            type="button"
            role="radio"
            :aria-checked="kind === item.kind"
            :class="{ active: kind === item.kind }"
            @click="pickKind(item.kind)"
          >
            <span class="provider-logo" aria-hidden="true"><img :src="PROVIDER_LOGOS[item.kind]" alt="" /></span>{{ item.label }}
          </button>
        </div>
        <span class="section-label">Cổng riêng (endpoint tương thích)</span>
        <div class="kind-picker gateways" role="radiogroup" aria-label="Cổng riêng">
          <button
            v-for="item in gateways"
            :key="item.kind"
            type="button"
            role="radio"
            :aria-checked="kind === item.kind"
            :class="{ active: kind === item.kind }"
            @click="pickKind(item.kind)"
          >
            <span class="provider-logo gateway" aria-hidden="true"><component :is="GATEWAY_ICONS[item.kind]" :size="20" /></span
            ><span class="kind-text"><strong>{{ GATEWAY_PROTOCOLS[item.kind] }}</strong><small>Tương thích</small></span>
          </button>
        </div>
      </template>
      <div class="field">
        <label for="provider-name">Tên hiển thị</label>
        <input id="provider-name" v-model="name" maxlength="120" required />
      </div>
      <div v-if="isGateway" class="field">
        <label for="provider-base">Địa chỉ cổng{{ dialog === 'edit' ? ' (để trống nếu giữ địa chỉ cũ)' : '' }}</label>
        <input
          id="provider-base"
          v-model="baseUrl"
          type="url"
          inputmode="url"
          maxlength="300"
          :required="dialog === 'add'"
          :placeholder="editing?.base_url || 'https://gateway.example.com/v1'"
        />
        <small class="muted">
          <template v-if="preview">Trợ lý sẽ gọi: <code>{{ preview }}</code></template>
          <template v-else>Nhập phần gốc của địa chỉ, ví dụ https://gateway.example.com hoặc …/v1.</template>
        </small>
        <small class="muted">
          Phải là HTTPS trên địa chỉ công khai. Cổng trong mạng nội bộ hoặc HTTP cần quản trị hệ thống thêm tên máy vào
          <code>ASSISTANT_ALLOWED_HOSTS</code>.
        </small>
      </div>
      <div class="field">
        <label for="provider-model">Model</label>
        <input id="provider-model" v-model="model" maxlength="120" required placeholder="Tên model trong tài khoản của bạn" />
        <small class="muted">{{
          isGateway ? 'Tên model cổng nhận, ví dụ “auto” để cổng tự chọn.' : 'Nhập đúng tên model tài khoản của bạn được dùng.'
        }}</small>
      </div>
      <div class="field">
        <label for="provider-key">Khóa API{{ dialog === 'edit' ? ' (để trống nếu giữ khóa cũ)' : '' }}</label>
        <input id="provider-key" v-model="apiKey" type="password" autocomplete="off" maxlength="500" :required="dialog === 'add'" />
        <small class="muted">{{ KIND_HINTS[kind] }}</small>
      </div>
      <div class="field" style="max-width: 240px">
        <label for="provider-tokens">Độ dài trả lời tối đa (token)</label>
        <input id="provider-tokens" v-model.number="maxTokens" type="number" min="256" max="64000" />
      </div>
      <div class="notice warning">
        Câu hỏi của người dùng và các đoạn kiến thức liên quan sẽ được gửi tới nhà cung cấp này để tạo câu trả lời.
      </div>
      <div class="form-actions">
        <button type="button" class="button secondary" :disabled="busy" @click="close">Hủy</button>
        <button class="button" :disabled="busy || !canSave">{{ busy ? 'Đang lưu…' : 'Lưu dịch vụ' }}</button>
      </div>
    </form>
  </ModalDialog>
</template>
