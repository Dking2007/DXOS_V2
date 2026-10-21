<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { useQuery } from '@tanstack/vue-query'
import { Files, FileText, ListChecks, MessageSquare, Newspaper, Search } from 'lucide-vue-next'
import { api } from '../api'
import { formatDate } from '@dx/web-shared/api.ts'
import StatePanel from '@dx/web-shared/components/StatePanel.vue'
import StatusBadge from '@dx/web-shared/components/StatusBadge.vue'
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
const router = useRouter()
const q = ref(String(route.query.q ?? ''))
const input = ref(q.value)
watch(
  () => route.query.q,
  (value) => {
    q.value = String(value ?? '')
    input.value = q.value
  },
)
const result = useQuery({
  queryKey: computed(() => ['search', q.value]),
  queryFn: () => api.request<Result>(`/search?q=${encodeURIComponent(q.value)}&limit=20`),
  enabled: computed(() => q.value.trim().length >= 2),
})
const groups = [
  { key: 'task', label: 'Công việc', icon: ListChecks },
  { key: 'case', label: 'Hồ sơ', icon: Files },
  { key: 'file', label: 'Tài liệu', icon: FileText },
  { key: 'post', label: 'Bảng tin', icon: Newspaper },
  { key: 'message', label: 'Tin nhắn', icon: MessageSquare },
]
function go() {
  router.push({ path: '/search', query: { q: input.value.trim() } })
}
</script>
<template>
  <header class="page-head">
    <div>
      <span class="eyebrow">TÌM KIẾM</span>
      <h1>Tìm trong không gian làm việc</h1>
      <p>Chỉ hiển thị và đếm những gì bạn được phép xem.</p>
    </div>
  </header>
  <form class="search-box search-large" @submit.prevent="go">
    <Search :size="19" /><input
      v-model="input"
      type="search"
      minlength="2"
      placeholder="Công việc, hồ sơ (vd. HS-000012), tài liệu, bài viết, tin nhắn…"
      aria-label="Từ khóa"
      autofocus
    /><button class="button small">Tìm</button>
  </form>
  <section v-if="q.length < 2" class="card" style="margin-top: 20px">
    <StatePanel :empty="true" title="Nhập ít nhất 2 ký tự" description="Tìm theo tiêu đề, nội dung, nhãn tài liệu hoặc mã hồ sơ." />
  </section>
  <template v-else>
    <section v-if="result.isPending.value || result.error.value" class="card" style="margin-top: 20px">
      <StatePanel :loading="result.isPending.value" :error="result.error.value" @retry="result.refetch()" />
    </section>
    <p v-else class="muted" style="margin: 18px 0">
      {{ result.data.value?.total ?? 0 }} kết quả cho “{{ q }}”
    </p>
    <div class="stack">
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
