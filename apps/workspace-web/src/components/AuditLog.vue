<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { useInfiniteQuery } from '@tanstack/vue-query'
import { api } from '../api'
import { formatDate } from '@dx/web-shared/api.ts'
import type { Page } from '@dx/web-shared/api.ts'
import StatePanel from '@dx/web-shared/components/StatePanel.vue'
import { auditLabel, auditLink } from '../ui/audit'
interface AuditEntry {
  id: string
  actor_id: string
  actor_name: string
  action: string
  resource_id: string
  created_at: string
}
const log = useInfiniteQuery({
  queryKey: ['audit-logs'],
  initialPageParam: '',
  queryFn: ({ pageParam }) =>
    api.request<Page<AuditEntry>>(`/audit-logs?limit=50${pageParam ? `&cursor=${encodeURIComponent(pageParam)}` : ''}`),
  getNextPageParam: (last) => last.next_cursor ?? undefined,
})
const entries = computed(() => log.data.value?.pages.flatMap((page) => page.items) ?? [])
</script>
<template>
  <section class="card">
    <header class="card-header">
      <div>
        <h2>Nhật ký hoạt động</h2>
        <p class="muted" style="font-size: 13px; margin-top: 5px">
          Ai đã làm gì, lúc nào trong không gian làm việc. Mới nhất ở trên.
        </p>
      </div>
    </header>
    <StatePanel
      :loading="log.isPending.value"
      :error="log.error.value"
      :empty="!!log.data.value && !entries.length"
      compact
      title="Chưa có hoạt động nào được ghi"
      @retry="log.refetch()"
    />
    <div v-if="entries.length" class="table-wrap">
      <table>
        <thead>
          <tr><th>Thời điểm</th><th>Người thực hiện</th><th>Hoạt động</th><th>Đối tượng</th></tr>
        </thead>
        <tbody>
          <tr v-for="entry in entries" :key="entry.id">
            <td>{{ formatDate(entry.created_at, true) }}</td>
            <td>{{ entry.actor_name }}</td>
            <td>{{ auditLabel(entry.action) }}</td>
            <td>
              <RouterLink v-if="auditLink(entry.action, entry.resource_id)" :to="auditLink(entry.action, entry.resource_id)!"
                >Mở</RouterLink
              ><code v-else class="muted">{{ entry.resource_id.slice(0, 8) }}</code>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-if="log.hasNextPage.value" class="card-body">
      <button class="button secondary" :disabled="log.isFetchingNextPage.value" @click="log.fetchNextPage()">
        Xem cũ hơn
      </button>
    </div>
  </section>
</template>
