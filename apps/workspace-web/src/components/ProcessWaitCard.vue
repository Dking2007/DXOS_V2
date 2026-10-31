<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { useQuery } from '@tanstack/vue-query'
import { api } from '../api'
import StatePanel from '@dx/web-shared/components/StatePanel.vue'
interface ProcessMetrics {
  period_days: number
  as_of: string
  sample_size: number
  truncated: boolean
  overdue_cases: number
  returns: number
  steps: { step: string; package_version_id: string | null; count: number; waiting: number; average_wait_hours: number | null; case_ids: string[] }[]
  suggestions: { kind: string; step?: string; sample_size: number; message: string; case_ids: string[] }[]
}
/** Where approvals wait longest, over the same period as the rest of the report. */
const props = defineProps<{ days: number }>()
const metrics = useQuery({
  queryKey: computed(() => ['process-metrics', props.days]),
  queryFn: () => api.request<ProcessMetrics>(`/process-metrics?days=${props.days}`),
})
const maxWait = computed(() =>
  Math.max(
    1,
    ...(metrics.data.value?.steps.map((step) => step.average_wait_hours ?? 0) ?? []),
  ),
)
</script>
<template>
  <section class="card" style="margin-top: 20px">
    <header class="card-header">
      <div><span class="eyebrow">CẢI TIẾN QUY TRÌNH</span><h2>Hồ sơ đang chờ lâu ở bước nào?</h2></div>
    </header>
    <div class="card-body">
      <StatePanel :loading="metrics.isPending.value" :error="metrics.error.value"
        :empty="metrics.data.value?.sample_size === 0" compact title="Chưa đủ hồ sơ để tính thời gian chờ"
        @retry="metrics.refetch()" />
      <template v-if="metrics.data.value?.sample_size">
        <p class="muted" style="font-size: 13px">Tính trên {{ metrics.data.value.sample_size }} lượt duyệt · {{ metrics.data.value.overdue_cases }} hồ sơ quá hạn · {{ metrics.data.value.returns }} lần trả lại<span v-if="metrics.data.value.truncated"> · chỉ lấy 2.000 lượt gần nhất</span></p>
        <div v-for="step in metrics.data.value.steps" :key="`${step.package_version_id}:${step.step}`" class="metric-row">
          <div><strong>{{ step.step }}</strong><small>{{ step.count }} lượt · {{ step.waiting }} đang chờ</small>
            <div v-if="step.case_ids.length" class="metric-cases"><RouterLink v-for="(caseId, n) in step.case_ids" :key="caseId" :to="`/cases/${caseId}`">Hồ sơ {{ n + 1 }}</RouterLink></div>
          </div>
          <div>
            <div class="metric-bar" aria-hidden="true"><span :style="{ width: `${((step.average_wait_hours ?? 0) / maxWait) * 100}%` }" /></div>
            <span class="metric-bar-label">Chờ trung bình {{ step.average_wait_hours === null ? 'chưa có' : `${step.average_wait_hours} giờ` }}</span>
          </div>
        </div>
        <div v-if="metrics.data.value.suggestions.length" class="notice" style="margin-top: 18px">
          <strong>Điểm cần kiểm tra</strong>
          <p v-for="suggestion in metrics.data.value.suggestions" :key="`${suggestion.kind}:${suggestion.step}`">{{ suggestion.step ? `${suggestion.step}: ` : '' }}{{ suggestion.message }}</p>
        </div>
      </template>
    </div>
  </section>
</template>
