<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { BookOpen, CheckCircle2, Circle, Cpu, Save, Settings2, Sparkles, Wand2 } from 'lucide-vue-next'
import type { AssistantAdmin } from '@dx/web-shared/types.ts'
import StatePanel from '@dx/web-shared/components/StatePanel.vue'
import { api } from '../api'
import { toast } from '../ui/toast'
import { useUnsavedGuard } from '../ui/unsaved'
import { assistantOpen } from '../assistant/state'
import ProviderPanel from '../assistant/ProviderPanel.vue'
import KnowledgePanel from '../assistant/KnowledgePanel.vue'
import AiSettingsPanel from '../ai/AiSettingsPanel.vue'
import { useAi } from '../ai/useAi'

const queryClient = useQueryClient()
const route = useRoute()
type Tab = 'overview' | 'providers' | 'knowledge' | 'features'
const requested = String(route.query.tab ?? '')
const tab = ref<Tab>((['overview', 'providers', 'knowledge', 'features'] as const).find((t) => t === requested) ?? 'overview')
const admin = useQuery({
  queryKey: ['assistant-admin'],
  queryFn: () => api.request<AssistantAdmin>('/assistant/admin'),
})

const enabled = ref(false)
const welcome = ref('')
const suggestions = ref('')
const instructions = ref('')
const dailyLimit = ref(50)
const saved = ref('')
function snapshot() {
  return JSON.stringify([enabled.value, welcome.value, suggestions.value, instructions.value, dailyLimit.value])
}
watch(
  () => admin.data.value?.config,
  (config) => {
    if (!config) return
    enabled.value = config.enabled
    welcome.value = config.welcome
    suggestions.value = config.suggestions.join('\n')
    instructions.value = config.instructions
    dailyLimit.value = config.daily_limit
    saved.value = snapshot()
  },
  { immediate: true },
)
const dirty = computed(() => !!saved.value && snapshot() !== saved.value)
useUnsavedGuard(dirty)

const busy = ref(false)
async function saveConfig() {
  if (!admin.data.value) return
  busy.value = true
  try {
    await api.request('/assistant/config', {
      method: 'PATCH',
      body: JSON.stringify({
        expected_revision: admin.data.value.config.revision,
        enabled: enabled.value,
        welcome: welcome.value,
        instructions: instructions.value,
        suggestions: suggestions.value.split('\n').map((line) => line.trim()).filter(Boolean).slice(0, 6),
        daily_limit: Number(dailyLimit.value) || 0,
      }),
    })
    toast.success(enabled.value ? 'Đã lưu. Trợ lý đang bật cho mọi người.' : 'Đã lưu cấu hình trợ lý.')
    await refresh()
  } catch (error) {
    toast.error(error)
  } finally {
    busy.value = false
  }
}
async function refresh() {
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: ['assistant-admin'] }),
    queryClient.invalidateQueries({ queryKey: ['assistant-status'] }),
  ])
}

const active = computed(() => admin.data.value?.providers.find((p) => p.active))
const ai = useAi()
const myData = computed(() => ai.on('assistant_my_data'))
const checklist = computed(() => {
  const data = admin.data.value
  if (!data) return []
  return [
    { done: !!active.value, text: 'Có dịch vụ AI đang dùng', go: 'providers' as Tab },
    { done: active.value?.last_test_ok === true, text: 'Đã kiểm tra kết nối thành công', go: 'providers' as Tab },
    { done: data.published_count > 0, text: `Có kiến thức (${data.published_count} bài đang dùng)`, go: 'knowledge' as Tab },
    { done: data.config.enabled, text: 'Đã bật trợ lý cho mọi người', go: 'overview' as Tab },
    {
      done: myData.value,
      text: myData.value
        ? 'Trả lời về dữ liệu của người hỏi: đang bật'
        : 'Trả lời về dữ liệu của người hỏi: đang tắt (không bắt buộc)',
      go: 'features' as Tab,
      optional: true,
    },
  ]
})
</script>
<template>
  <header class="page-head compact">
    <h1 class="sr-only">Trợ lý AI</h1>
    <button class="button secondary" type="button" @click="assistantOpen = true">
      <Sparkles :size="16" />Thử hỏi trợ lý
    </button>
  </header>
  <nav class="subnav" aria-label="Phần cài đặt trợ lý">
    <button :class="{ active: tab === 'overview' }" @click="tab = 'overview'"><Settings2 :size="15" /> Cấu hình chung</button>
    <button :class="{ active: tab === 'providers' }" @click="tab = 'providers'"><Cpu :size="15" /> Dịch vụ AI</button>
    <button :class="{ active: tab === 'knowledge' }" @click="tab = 'knowledge'"><BookOpen :size="15" /> Kiến thức</button>
    <button :class="{ active: tab === 'features' }" @click="tab = 'features'"><Wand2 :size="15" /> Tính năng AI</button>
  </nav>
  <StatePanel
    v-if="!admin.data.value"
    :loading="admin.isPending.value"
    :error="admin.error.value"
    @retry="admin.refetch()"
  />
  <template v-else>
    <div v-if="tab === 'overview'" class="split">
      <section class="card">
        <header class="card-header"><h2>Cấu hình chung</h2></header>
        <form class="card-body stack" @submit.prevent="saveConfig">
          <label class="assistant-toggle">
            <span class="switch"><input v-model="enabled" type="checkbox" /><span /></span>
            <span
              ><strong>Bật trợ lý cho mọi người</strong
              ><small>Khi bật, mọi tài khoản thấy nút trợ lý ở góc màn hình.</small></span
            >
          </label>
          <div class="field">
            <label for="assistant-welcome">Lời chào</label>
            <textarea id="assistant-welcome" v-model="welcome" rows="2" maxlength="1000" />
          </div>
          <div class="field">
            <label for="assistant-suggestions">Câu hỏi gợi ý (mỗi dòng một câu, tối đa 6)</label>
            <textarea id="assistant-suggestions" v-model="suggestions" rows="4" />
          </div>
          <div class="field">
            <label for="assistant-instructions">Hướng dẫn thêm cho trợ lý (không bắt buộc)</label>
            <textarea
              id="assistant-instructions"
              v-model="instructions"
              rows="4"
              maxlength="4000"
              placeholder="Ví dụ: Xưng “anh/chị”. Khi hỏi về nghỉ phép, nhắc nộp đơn trước 3 ngày."
            />
          </div>
          <div class="field" style="max-width: 260px">
            <label for="assistant-limit">Số câu hỏi tối đa mỗi người mỗi ngày</label>
            <input id="assistant-limit" v-model.number="dailyLimit" type="number" min="0" max="10000" />
            <small class="muted">0 là không giới hạn. Giới hạn giúp kiểm soát chi phí dịch vụ AI.</small>
          </div>
          <div class="form-actions">
            <button class="button" :disabled="busy || !dirty"><Save :size="16" />{{ busy ? 'Đang lưu…' : 'Lưu cấu hình' }}</button>
          </div>
        </form>
      </section>
      <aside class="stack" style="align-content: start">
        <section class="card">
          <header class="card-header"><h3>Mức sẵn sàng</h3></header>
          <ul class="assistant-checklist">
            <li v-for="item in checklist" :key="item.text" :class="{ done: item.done }">
              <CheckCircle2 v-if="item.done" :size="18" /><Circle v-else :size="18" />
              <span>{{ item.text }}</span>
              <button v-if="!item.done && item.go !== 'overview'" type="button" class="link-button" @click="tab = item.go">
                {{ 'optional' in item ? 'Xem' : 'Làm ngay' }}
              </button>
            </li>
          </ul>
        </section>
        <div class="notice">
          <Sparkles :size="18" /><span
            >Trợ lý luôn trả lời từ phần <strong>Kiến thức</strong>. Khi bật “Trợ lý trả lời về dữ liệu của người hỏi” ở
            tab <strong>Tính năng AI</strong>
            <template v-if="myData">(đang bật)</template><template v-else>(đang tắt)</template>, trợ lý xem thêm những
            gì chính người hỏi mở được: công việc được giao, đã giao, điều phối hoặc theo dõi; bàn giao việc và ủy quyền
            phê duyệt; hồ sơ của họ và hồ sơ đang chờ họ duyệt; tài liệu của họ, tài liệu được chia sẻ với họ và đã chia
            sẻ cho người khác. Trợ lý không bao giờ xem dữ liệu ngoài quyền của người hỏi. Câu hỏi được gửi tới dịch vụ
            AI bạn chọn.</span
          >
        </div>
      </aside>
    </div>
    <ProviderPanel
      v-if="tab === 'providers'"
      :providers="admin.data.value.providers"
      :kinds="admin.data.value.kinds"
      :allowed-hosts="admin.data.value.allowed_hosts"
      @changed="refresh"
    />
    <KnowledgePanel v-if="tab === 'knowledge'" :categories="admin.data.value.categories" @changed="refresh" />
    <AiSettingsPanel v-if="tab === 'features'" />
  </template>
</template>
