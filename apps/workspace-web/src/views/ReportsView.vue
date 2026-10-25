<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { useQuery } from '@tanstack/vue-query'
import {
  AlarmClock,
  CheckCheck,
  ClipboardCheck,
  Download,
  HardDrive,
  ListChecks,
  Undo2,
  Workflow,
} from 'lucide-vue-next'
import { api } from '../api'
import { formatDate, formatSize } from '@dx/web-shared/api.ts'
import StatePanel from '@dx/web-shared/components/StatePanel.vue'
import StatusBadge from '@dx/web-shared/components/StatusBadge.vue'
interface Overview {
  as_of: string
  period_days: number
  definitions: Record<string, string>
  tasks: {
    total: number
    by_status: Record<string, number>
    open: number
    open_with_due: number
    overdue: number
    overdue_rate: number | null
    completed_in_period: number
    completed_late: number
    late_completion_rate: number | null
    average_completion_hours: number | null
    by_assignee: { assignee_id: string | null; display_name: string; open: number; overdue: number }[]
  }
  cases: {
    total: number
    by_status: Record<string, number>
    returns_in_period: number
    pending_my_approval: number
  }
  storage: { my_files: number; my_bytes: number }
  automations?: { failed_in_period: number; enabled_rules: number }
}
const days = ref(30)
const scope = ref<'all' | 'mine' | 'managed'>('all')
const report = useQuery({
  queryKey: computed(() => ['reports', days.value, scope.value]),
  queryFn: () => api.request<Overview>(`/reports/overview?days=${days.value}&scope=${scope.value}`),
})
const data = computed(() => report.data.value)
function percent(value: number | null | undefined) {
  return value === null || value === undefined ? '—' : `${Math.round(value * 100)}%`
}
function bars(record: Record<string, number>) {
  const max = Math.max(1, ...Object.values(record))
  return Object.entries(record)
    .sort((a, b) => b[1] - a[1])
    .map(([status, count]) => ({ status, count, width: (count / max) * 100 }))
}
</script>
<template>
  <header class="page-head">
    <div>
      <span class="eyebrow">BÁO CÁO VÀ ĐIỀU HÀNH</span>
      <h1>Báo cáo</h1>
      <p>Số liệu tính trên dữ liệu bạn được phép xem; mỗi chỉ số có định nghĩa rõ ràng.</p>
    </div>
    <div class="page-actions">
      <select v-model="scope" aria-label="Phạm vi" class="compact-select">
        <option value="all">Mọi việc tôi xem được</option>
        <option value="managed">Việc tôi giao / điều phối</option>
        <option value="mine">Việc của tôi</option>
      </select>
      <select v-model.number="days" aria-label="Khoảng thời gian" class="compact-select">
        <option :value="7">7 ngày</option>
        <option :value="30">30 ngày</option>
        <option :value="90">90 ngày</option>
        <option :value="365">12 tháng</option>
      </select>
      <a class="button secondary" :href="`/workspace/v1/reports/tasks.csv?scope=${scope}`"
        ><Download :size="16" />Xuất CSV</a
      >
    </div>
  </header>
  <section v-if="report.isPending.value || report.error.value" class="card">
    <StatePanel
      :loading="report.isPending.value"
      :error="report.error.value"
      @retry="report.refetch()"
    />
  </section>
  <template v-if="data">
    <p class="muted" style="font-size: 13px; margin-bottom: 14px">
      Cập nhật lúc {{ formatDate(data.as_of, true) }} (tính khi tải trang, không phải thời gian
      thực).
    </p>
    <div class="stat-grid">
      <RouterLink to="/tasks?scope=all&status=assigned,accepted,in_progress,blocked,returned,submitted" class="stat-tile">
        <span class="stat-icon"><ListChecks :size="21" /></span>
        <div><strong>{{ data.tasks.open }}</strong><small>Việc đang mở</small></div>
      </RouterLink>
      <RouterLink to="/tasks?scope=all&overdue=true" class="stat-tile">
        <span class="stat-icon red"><AlarmClock :size="21" /></span>
        <div>
          <strong>{{ data.tasks.overdue }}</strong
          ><small>Quá hạn · {{ percent(data.tasks.overdue_rate) }} việc có hạn</small>
        </div>
      </RouterLink>
      <div class="stat-tile">
        <span class="stat-icon blue"><CheckCheck :size="21" /></span>
        <div>
          <strong>{{ data.tasks.completed_in_period }}</strong
          ><small
            >Hoàn tất trong kỳ · trễ {{ percent(data.tasks.late_completion_rate) }}</small
          >
        </div>
      </div>
      <RouterLink to="/approvals" class="stat-tile">
        <span class="stat-icon amber"><ClipboardCheck :size="21" /></span>
        <div>
          <strong>{{ data.cases.pending_my_approval }}</strong><small>Hồ sơ chờ tôi duyệt</small>
        </div>
      </RouterLink>
    </div>
    <div class="home-columns">
      <div class="stack">
        <section class="card">
          <header class="card-header">
            <div><span class="eyebrow">CÔNG VIỆC</span><h2>Theo trạng thái</h2></div>
            <span class="muted" style="font-size: 13px"
              >TB hoàn tất:
              {{
                data.tasks.average_completion_hours === null
                  ? '—'
                  : `${data.tasks.average_completion_hours} giờ`
              }}</span
            >
          </header>
          <div class="card-body">
            <p v-if="!data.tasks.total" class="muted">Chưa có công việc trong phạm vi.</p>
            <div v-for="row in bars(data.tasks.by_status)" :key="row.status" class="bar-row">
              <StatusBadge :status="row.status" />
              <div class="metric-bar"><span :style="{ width: `${row.width}%` }" /></div>
              <strong>{{ row.count }}</strong>
            </div>
          </div>
        </section>
        <section class="card">
          <header class="card-header">
            <div><span class="eyebrow">PHÂN BỔ</span><h2>Việc đang mở theo người</h2></div>
          </header>
          <div v-if="data.tasks.by_assignee.length" class="table-wrap">
            <table>
              <thead>
                <tr><th>Người phụ trách</th><th>Đang mở</th><th>Quá hạn</th></tr>
              </thead>
              <tbody>
                <tr v-for="row in data.tasks.by_assignee" :key="row.assignee_id ?? 'none'">
                  <td>{{ row.display_name }}</td>
                  <td>{{ row.open }}</td>
                  <td :class="{ 'overdue-text': row.overdue }">{{ row.overdue }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-else class="card-body muted">Không có việc đang mở.</p>
        </section>
      </div>
      <aside class="stack" style="align-content: start">
        <section class="card">
          <header class="card-header">
            <div><span class="eyebrow">HỒ SƠ</span><h2>{{ data.cases.total }} hồ sơ</h2></div>
            <span class="muted" style="font-size: 13px"
              ><Undo2 :size="14" /> {{ data.cases.returns_in_period }} lần trả lại</span
            >
          </header>
          <div class="card-body">
            <div v-for="row in bars(data.cases.by_status)" :key="row.status" class="bar-row">
              <StatusBadge :status="row.status" />
              <div class="metric-bar"><span :style="{ width: `${row.width}%` }" /></div>
              <strong>{{ row.count }}</strong>
            </div>
          </div>
        </section>
        <section class="card">
          <div class="card-body stack">
            <div class="date-line"><HardDrive :size="16" /> Tài liệu của tôi</div>
            <p>
              <strong>{{ data.storage.my_files }}</strong> tệp ·
              {{ formatSize(data.storage.my_bytes) }}
            </p>
            <template v-if="data.automations">
              <div class="date-line"><Workflow :size="16" /> Tự động hóa</div>
              <p>
                {{ data.automations.enabled_rules }} luật đang bật ·
                <span :class="{ 'overdue-text': data.automations.failed_in_period }"
                  >{{ data.automations.failed_in_period }} lượt lỗi trong kỳ</span
                >
              </p>
            </template>
          </div>
        </section>
        <section class="card">
          <header class="card-header"><h3>Định nghĩa chỉ số</h3></header>
          <dl class="card-body detail-meta">
            <div><dt>Tỷ lệ quá hạn</dt><dd>{{ data.definitions.overdue_rate }}</dd></div>
            <div><dt>Tỷ lệ hoàn tất trễ</dt><dd>{{ data.definitions.late_completion_rate }}</dd></div>
            <div><dt>Việc đã hủy</dt><dd>{{ data.definitions.cancelled }}</dd></div>
          </dl>
        </section>
      </aside>
    </div>
  </template>
</template>
