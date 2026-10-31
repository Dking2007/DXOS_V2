<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { Database, Eye, ListRestart, Plug, RefreshCw, Save } from 'lucide-vue-next'
import StatePanel from '@dx/web-shared/components/StatePanel.vue'
import { api } from '../api'
import { toast } from '../ui/toast'
import { useUnsavedGuard } from '../ui/unsaved'
import { RECOMMENDED_FEATURES } from './useAi'

interface Feature {
  key: string
  group: string
  label: string
  description: string
  needs_vision: boolean
  enabled: boolean
  provider_id: string | null
  model: string
}
interface Provider {
  id: string
  name: string
  kind: string
  model: string
  active: boolean
  embeds: boolean
  reads_pdf: boolean
  sees_images: boolean
}
interface Settings {
  revision: number
  groups: { key: string; label: string }[]
  features: Feature[]
  embedding: { provider_id: string | null; model: string }
  providers: Provider[]
  index: { ready: boolean; indexed: number; total: number; by_type: Record<string, number> }
}
// A model name that works out of the box for each kind that makes vectors.
const EMBED_MODELS: Record<string, string> = {
  ollama: 'bge-m3',
  openai: 'text-embedding-3-small',
  gemini: 'gemini-embedding-001',
  vllm: 'BAAI/bge-m3',
  custom_chat: 'text-embedding-3-small',
}

const queryClient = useQueryClient()
const settings = useQuery({ queryKey: ['ai-settings'], queryFn: () => api.request<Settings>('/ai/settings') })
const choices = ref<Record<string, { enabled: boolean; provider_id: string | null; model: string }>>({})
const embedProvider = ref<string>('')
const embedModel = ref('')
const busy = ref(false)
const testing = ref(false)
const saved = ref('')
function state() {
  return JSON.stringify([choices.value, embedProvider.value, embedModel.value])
}
watch(
  () => settings.data.value,
  (data) => {
    if (!data) return
    choices.value = Object.fromEntries(
      data.features.map((f) => [f.key, { enabled: f.enabled, provider_id: f.provider_id, model: f.model }]),
    )
    embedProvider.value = data.embedding.provider_id ?? ''
    embedModel.value = data.embedding.model
    saved.value = state()
  },
  { immediate: true },
)
const dirty = computed(() => !!saved.value && state() !== saved.value)
useUnsavedGuard(dirty)
const active = computed(() => settings.data.value?.providers.find((p) => p.active))
const embedders = computed(() => settings.data.value?.providers.filter((p) => p.embeds) ?? [])
const enabledCount = computed(() => Object.values(choices.value).filter((c) => c.enabled).length)
function providerOf(key: string) {
  const id = choices.value[key]?.provider_id
  return settings.data.value?.providers.find((p) => p.id === id) ?? active.value
}
function visionWarning(feature: Feature) {
  const provider = providerOf(feature.key)
  return feature.needs_vision && provider && !provider.sees_images
}
watch(embedProvider, (id, old) => {
  const kind = settings.data.value?.providers.find((p) => p.id === id)?.kind
  if (old !== undefined && kind && (!embedModel.value || old)) embedModel.value = EMBED_MODELS[kind] ?? ''
})
// Models each service offers, fetched once per service and purpose, to pick from per feature.
const models = ref<Record<string, string[]>>({})
const loadingModels = ref<Record<string, boolean>>({})
const modelErrors = ref<Record<string, string>>({})
function listKey(providerId: string, purpose: 'chat' | 'embed') {
  return `${providerId}:${purpose}`
}
async function loadModels(providerId: string | null | undefined, purpose: 'chat' | 'embed', force = false) {
  const provider = settings.data.value?.providers.find((p) => p.id === providerId)
  if (!provider) return
  const key = listKey(provider.id, purpose)
  if ((models.value[key] && !force) || loadingModels.value[key]) return
  loadingModels.value[key] = true
  delete modelErrors.value[key]
  try {
    const result = await api.request<{ models: string[] }>('/assistant/models', {
      method: 'POST',
      body: JSON.stringify({ kind: provider.kind, provider_id: provider.id, purpose }),
    })
    models.value[key] = result.models
  } catch (error) {
    models.value[key] = []
    modelErrors.value[key] = error instanceof Error ? error.message : 'Không lấy được danh sách model'
  } finally {
    loadingModels.value[key] = false
  }
}
function chooseProvider(key: string, providerId: string | null) {
  const choice = choices.value[key]
  if (choice.provider_id === providerId) return
  choice.provider_id = providerId
  choice.model = ''
  void loadModels(providerId, 'chat')
}
watch(
  () => settings.data.value,
  (data) => {
    if (!data) return
    const active = data.providers.find((p) => p.active)?.id
    for (const id of new Set([active, ...data.features.map((f) => f.provider_id)].filter(Boolean))) void loadModels(id, 'chat')
    if (data.embedding.provider_id) void loadModels(data.embedding.provider_id, 'embed')
  },
  { immediate: true },
)
watch(embedProvider, (id) => id && loadModels(id, 'embed'))
/** The service a feature actually uses: its own choice, else the assistant's active one. */
function serviceOf(key: string): string | null {
  return choices.value[key]?.provider_id ?? active.value?.id ?? null
}
function listOf(key: string) {
  const id = serviceOf(key)
  return id ? models.value[listKey(id, 'chat')] : undefined
}
/** A model belongs to a service, so picking one on "the active service" pins that service. */
function chooseModel(key: string, model: string) {
  const choice = choices.value[key]
  choice.model = model.trim()
  if (choice.model && !choice.provider_id) choice.provider_id = serviceOf(key)
}
function defaultModel(providerId: string | null) {
  return settings.data.value?.providers.find((p) => p.id === providerId)?.model ?? ''
}
const RECOMMENDED: string[] = RECOMMENDED_FEATURES
function recommended() {
  for (const [key, choice] of Object.entries(choices.value)) choice.enabled = RECOMMENDED.includes(key)
  toast.success('Đã chọn gói khuyến nghị. Bấm “Lưu cấu hình” để áp dụng.')
}
function setAll(value: boolean) {
  for (const key of Object.keys(choices.value)) choices.value[key].enabled = value
}

async function save() {
  if (!settings.data.value) return
  busy.value = true
  try {
    await api.request('/ai/settings', {
      method: 'PUT',
      body: JSON.stringify({
        expected_revision: settings.data.value.revision,
        features: choices.value,
        embedding: { provider_id: embedProvider.value || null, model: embedModel.value },
      }),
    })
    toast.success('Đã lưu cấu hình tính năng AI')
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['ai-settings'] }),
      queryClient.invalidateQueries({ queryKey: ['ai-features'] }),
    ])
  } catch (error) {
    toast.error(error)
  } finally {
    busy.value = false
  }
}
async function testEmbedding() {
  testing.value = true
  try {
    const result = await api.request<{ ok: boolean; message: string }>('/ai/settings/test-embedding', {
      method: 'POST',
      body: JSON.stringify({ provider_id: embedProvider.value, model: embedModel.value }),
    })
    if (result.ok) toast.success(result.message)
    else toast.error(result.message)
  } catch (error) {
    toast.error(error)
  } finally {
    testing.value = false
  }
}
async function reindex() {
  try {
    await api.request('/ai/index', { method: 'POST' })
    toast.success('Đã xếp lịch lập chỉ mục. Việc này chạy nền, có thể mất vài phút.')
  } catch (error) {
    toast.error(error)
  }
}
</script>
<template>
  <StatePanel v-if="!settings.data.value" :loading="settings.isPending.value" :error="settings.error.value" @retry="settings.refetch()" />
  <template v-else>
    <div v-if="active && !enabledCount" class="notice" style="margin-bottom: 16px">
      <span class="grow"
        >Chưa bật tính năng AI nào. Gói khuyến nghị bật {{ RECOMMENDED.length }} tính năng chỉ đọc những gì người dùng đã
        được xem và trả lời bằng chữ; bạn vẫn xem lại được trước khi lưu.</span
      >
      <button type="button" class="button small" @click="recommended">Dùng gói khuyến nghị</button>
    </div>
    <div v-if="!active" class="notice warning" style="margin-bottom: 16px">
      Chưa có dịch vụ AI đang dùng. Thêm và chọn một dịch vụ ở tab <strong>Dịch vụ AI</strong> trước; các tính năng
      dưới đây dùng dịch vụ đó nếu bạn không chọn riêng.
    </div>
    <form class="stack" @submit.prevent="save">
      <section v-for="group in settings.data.value.groups" :key="group.key" class="card">
        <header class="card-header"><h2>{{ group.label }}</h2></header>
        <div class="card-body">
          <div
            v-for="feature in settings.data.value.features.filter((f) => f.group === group.key)"
            :key="feature.key"
            class="ai-feature-row"
          >
            <input
              :id="`ai-${feature.key}`"
              v-model="choices[feature.key].enabled"
              type="checkbox"
              :aria-describedby="`ai-${feature.key}-hint`"
            />
            <label :for="`ai-${feature.key}`">
              <strong>{{ feature.label }}</strong>
              <small :id="`ai-${feature.key}-hint`">{{ feature.description }}</small>
              <small v-if="feature.needs_vision" class="muted"
                ><Eye :size="12" /> Tệp scan, ảnh chụp cần dịch vụ đọc được ảnh (Claude, OpenAI, Gemini, model có
                thị giác trên Ollama/vLLM).</small
              >
              <small v-if="visionWarning(feature)" style="color: var(--red-ink)"
                >Dịch vụ đang chọn chỉ đọc chữ: tài liệu scan sẽ không đọc được.</small
              >
            </label>
            <div class="ai-model-pick">
              <select
                :value="choices[feature.key].provider_id ?? ''"
                :aria-label="`Dịch vụ AI cho ${feature.label}`"
                @change="chooseProvider(feature.key, ($event.target as HTMLSelectElement).value || null)"
              >
                <option value="">Dịch vụ đang dùng{{ active ? ` (${active.name} · ${active.model})` : '' }}</option>
                <option v-for="provider in settings.data.value.providers" :key="provider.id" :value="provider.id">
                  {{ provider.name }}
                </option>
              </select>
              <div v-if="serviceOf(feature.key)" class="inline-actions">
                <select
                  v-if="listOf(feature.key)?.length"
                  :value="choices[feature.key].model"
                  class="grow"
                  :aria-label="`Model cho ${feature.label}`"
                  @change="chooseModel(feature.key, ($event.target as HTMLSelectElement).value)"
                >
                  <option value="">Model mặc định ({{ defaultModel(serviceOf(feature.key)) }})</option>
                  <option v-for="name in listOf(feature.key)" :key="name" :value="name">{{ name }}</option>
                  <option
                    v-if="choices[feature.key].model && !listOf(feature.key)!.includes(choices[feature.key].model)"
                    :value="choices[feature.key].model"
                  >
                    {{ choices[feature.key].model }} (không còn trong danh sách)
                  </option>
                </select>
                <input
                  v-else
                  :value="choices[feature.key].model"
                  class="grow"
                  maxlength="120"
                  :aria-label="`Model cho ${feature.label}`"
                  :placeholder="
                    loadingModels[listKey(serviceOf(feature.key)!, 'chat')]
                      ? 'Đang lấy danh sách model…'
                      : `Mặc định: ${defaultModel(serviceOf(feature.key))}`
                  "
                  @change="chooseModel(feature.key, ($event.target as HTMLInputElement).value)"
                />
                <button
                  type="button"
                  class="icon-button"
                  title="Lấy lại danh sách model"
                  aria-label="Lấy lại danh sách model"
                  :disabled="loadingModels[listKey(serviceOf(feature.key)!, 'chat')]"
                  @click="loadModels(serviceOf(feature.key), 'chat', true)"
                >
                  <ListRestart :size="15" />
                </button>
              </div>
              <small v-if="serviceOf(feature.key) && modelErrors[listKey(serviceOf(feature.key)!, 'chat')]" class="muted">
                Không lấy được danh sách model của dịch vụ này; gõ tên model hoặc để trống.
              </small>
            </div>
          </div>
        </div>
      </section>

      <section class="card">
        <header class="card-header">
          <div>
            <h2><Database :size="18" /> Tìm theo ý nghĩa</h2>
            <p class="muted" style="font-size: 13px; margin-top: 4px">
              Cần một dịch vụ tạo vector (embedding): Ollama, OpenAI, Gemini, vLLM hoặc cổng Chat Completions. Nội
              dung tài liệu, công việc, hồ sơ được gửi tới dịch vụ này để lập chỉ mục.
            </p>
          </div>
        </header>
        <div class="card-body stack">
          <div class="form-grid">
            <div class="field">
              <label for="embed-provider">Dịch vụ tạo vector</label>
              <select id="embed-provider" v-model="embedProvider">
                <option value="">Tắt tìm theo ý nghĩa</option>
                <option v-for="provider in embedders" :key="provider.id" :value="provider.id">
                  {{ provider.name }} ({{ provider.kind }})
                </option>
              </select>
              <small v-if="!embedders.length" class="muted">Chưa có dịch vụ nào tạo được vector.</small>
            </div>
            <div class="field">
              <label for="embed-model">Model tạo vector</label>
              <input
                id="embed-model"
                v-model="embedModel"
                maxlength="120"
                list="embed-models"
                :disabled="!embedProvider"
                placeholder="bge-m3"
              />
              <datalist id="embed-models">
                <option v-for="name in models[listKey(embedProvider, 'embed')] ?? []" :key="name" :value="name" />
              </datalist>
              <small v-if="embedProvider && models[listKey(embedProvider, 'embed')]?.length" class="muted">
                Dịch vụ có {{ models[listKey(embedProvider, 'embed')].length }} model tạo vector; bấm vào ô để chọn.
              </small>
              <small v-else-if="embedProvider && models[listKey(embedProvider, 'embed')]" class="muted">
                Không thấy model tạo vector nào. Với Ollama, tải về bằng <code>ollama pull bge-m3</code>.
              </small>
            </div>
          </div>
          <div class="inline-actions">
            <button type="button" class="button secondary small" :disabled="!embedProvider || !embedModel || testing" @click="testEmbedding">
              <Plug :size="14" />{{ testing ? 'Đang thử…' : 'Thử tạo vector' }}
            </button>
            <button type="button" class="button secondary small" :disabled="!settings.data.value.index.ready || dirty" @click="reindex">
              <RefreshCw :size="14" />Lập chỉ mục lại
            </button>
            <span v-if="settings.data.value.index.ready" class="muted" style="font-size: 13px">
              Đã lập chỉ mục {{ settings.data.value.index.indexed }}/{{ settings.data.value.index.total }} mục
              ({{ settings.data.value.index.by_type.file ?? 0 }} tài liệu, {{ settings.data.value.index.by_type.task ?? 0 }}
              công việc, {{ settings.data.value.index.by_type.case ?? 0 }} hồ sơ).
            </span>
          </div>
        </div>
      </section>

      <div class="form-actions sticky-actions">
        <span class="muted grow" style="font-size: 13px">
          Đang bật {{ enabledCount }}/{{ settings.data.value.features.length }} tính năng. Mỗi lần dùng tính năng AI
          tính vào giới hạn lượt/người/ngày ở tab Cấu hình chung.
        </span>
        <button type="button" class="button secondary" @click="recommended">Gói khuyến nghị</button>
        <button type="button" class="button secondary" @click="setAll(true)">Bật tất cả</button>
        <button type="button" class="button secondary" @click="setAll(false)">Tắt tất cả</button>
        <button class="button" :disabled="busy || !dirty"><Save :size="16" />{{ busy ? 'Đang lưu…' : 'Lưu cấu hình' }}</button>
      </div>
    </form>
  </template>
</template>
