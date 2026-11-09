<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { useQuery } from '@tanstack/vue-query'
import { Files, FileText, ListChecks, MessageSquare, Newspaper, Search, Sparkles } from 'lucide-vue-next'
import { api } from '../api'
import { formatDate } from '@dx/web-shared/api.ts'
import StatePanel from '@dx/web-shared/components/StatePanel.vue'
import StatusBadge from '@dx/web-shared/components/StatusBadge.vue'
import { useAi } from '../ai/useAi'
import { openPalette } from '../ui/palette'
interface Hit {
  type: string
  id: string
  title: string
  snippet: string
  status?: string
  link: string
  updated_at: string
}
interface Result {
  total: number
  groups: Record<string, { total: number; items: Hit[] }>
}
const route = useRoute()
const q = ref(String(route.query.q ?? ''))
watch(
  () => route.query.q,
  (value) => {
    q.value = String(value ?? '')
  },
)
const result = useQuery({
  queryKey: computed(() => ['search', q.value]),
  queryFn: () => api.request<Result>(`/search?q=${encodeURIComponent(q.value)}&limit=20`),
  enabled: computed(() => q.value.trim().length >= 2),
})
const ai = useAi()
interface MeaningHit {
  type: 'file' | 'task' | 'case'
  id: string
  title: string
  link: string
  snippet: string
  score: number
}
// Search by meaning runs beside the word search, for content worded differently from the query.
const meaning = useQuery({
  queryKey: computed(() => ['ai-search', q.value]),
  queryFn: () =>
    api.request<{ items: MeaningHit[] }>('/ai/search', { method: 'POST', body: JSON.stringify({ q: q.value.trim() }) }),
  enabled: computed(() => q.value.trim().length >= 2 && ai.on('semantic_search') && ai.semanticReady.value),
  staleTime: 60_000,
  retry: false,
})
const TYPE_LABEL = { file: 'Tài liệu', task: 'Công việc', case: 'Hồ sơ' }
const groups = [
  { key: 'task', label: 'Công việc', icon: ListChecks },
  { key: 'case', label: 'Hồ sơ', icon: Files },
  { key: 'file', label: 'Tài liệu', icon: FileText },
  { key: 'post', label: 'Bảng tin', icon: Newspaper },
  { key: 'message', label: 'Tin nhắn', icon: MessageSquare },
]
</script>
<template>
  <header class="page-head compact">
    <h1 class="sr-only">Tìm kiếm</h1>
  </header>
  <div class="search-refine">
    <span v-if="q.length >= 2"
      >Kết quả tìm cho <strong>“{{ q }}”</strong></span
    ><span v-else class="muted">Gõ từ khóa vào ô tìm kiếm trên thanh trên cùng (Ctrl K).</span>
    <button class="button secondary small" type="button" @click="openPalette(q)">
      <Search :size="15" />{{ q.length >= 2 ? 'Đổi từ khóa' : 'Mở ô tìm kiếm' }}
    </button>
  </div>
  <section v-if="q.length < 2" class="card" style="margin-top: 20px">
    <StatePanel
      :empty="true"
      title="Nhập ít nhất 2 ký tự"
      description="Tìm theo tiêu đề, nội dung, nhãn tài liệu hoặc mã hồ sơ (ví dụ HS-000012)."
    />
  </section>
  <template v-else>
    <section v-if="result.isPending.value || result.error.value" class="card" style="margin-top: 20px">
      <StatePanel :loading="result.isPending.value" :error="result.error.value" @retry="result.refetch()" />
    </section>
    <p v-else class="muted" style="margin: 18px 0">
      {{ result.data.value?.total ?? 0 }} kết quả cho “{{ q }}”
    </p>
    <div class="stack">
      <section v-if="ai.on('semantic_search') && ai.semanticReady.value" class="ai-card">
        <header><span class="ai-title"><Sparkles :size="16" />Kết quả theo ý nghĩa</span></header>
        <p v-if="meaning.isPending.value" class="muted">AI đang tìm nội dung có ý nghĩa gần với “{{ q }}”…</p>
        <p v-else-if="meaning.error.value" class="muted">Chưa tìm theo ý nghĩa được lúc này.</p>
        <p v-else-if="!meaning.data.value?.items.length" class="muted">Không có nội dung nào gần nghĩa.</p>
        <RouterLink
          v-for="hit in meaning.data.value?.items"
          :key="`${hit.type}:${hit.id}`"
          :to="hit.link"
          class="list-row"
          style="color: inherit; text-decoration: none"
        >
          <div class="grow">
            <p>{{ hit.title }}</p>
            <small>{{ hit.snippet }}</small>
          </div>
          <span class="tag">{{ TYPE_LABEL[hit.type] }}</span>
        </RouterLink>
      </section>
      <template v-for="group in groups" :key="group.key">
        <section v-if="result.data.value?.groups[group.key]?.total" class="card">
          <header class="card-header">
            <h2>
              <component :is="group.icon" :size="18" style="vertical-align: -3px" />
              {{ group.label }}
            </h2>
            <span class="muted">{{ result.data.value.groups[group.key].total }}</span>
          </header>
          <RouterLink
            v-for="hit in result.data.value.groups[group.key].items"
            :key="hit.id"
            :to="hit.link"
            class="list-row"
            style="color: inherit; text-decoration: none"
          >
            <div class="grow">
              <p>{{ hit.title }}</p>
              <small>{{ hit.snippet }}</small>
            </div>
            <StatusBadge v-if="hit.status" :status="hit.status" />
            <small class="muted">{{ formatDate(hit.updated_at) }}</small>
          </RouterLink>
        </section>
      </template>
    </div>
  </template>
</template>
