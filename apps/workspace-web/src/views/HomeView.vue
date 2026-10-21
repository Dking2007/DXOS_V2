<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { useQuery } from '@tanstack/vue-query'
import {
  AlarmClock,
  ArrowRight,
  CalendarDays,
  ClipboardCheck,
  FilePlus2,
  FolderClosed,
  History,
  ListChecks,
  ShieldCheck,
  Undo2,
} from 'lucide-vue-next'
import { api } from '../api'
import { useSession } from '../stores/session'
import type { Page } from '@dx/web-shared/api.ts'
import { formatDate } from '@dx/web-shared/api.ts'
import type { ApprovalTask, CaseItem, Task } from '@dx/web-shared/types.ts'
import StatePanel from '@dx/web-shared/components/StatePanel.vue'
import StatusBadge from '@dx/web-shared/components/StatusBadge.vue'
const session = useSession()
const today = new Intl.DateTimeFormat('vi-VN', {
  weekday: 'long',
  day: 'numeric',
  month: 'long',
  year: 'numeric',
}).format(new Date())
const firstName = computed(
  () => session.user?.display_name.split(' ').slice(-1)[0] ?? '',
)
const approvals = useQuery({
  queryKey: ['approvals', 'home'],
  queryFn: () => api.request<Page<ApprovalTask>>('/approval-tasks'),
})
const myTasks = useQuery({
  queryKey: ['tasks', 'home'],
  queryFn: () =>
    api.request<Page<Task>>(
      '/tasks?scope=mine&status=assigned,accepted,in_progress,blocked,returned&limit=50',
    ),
})
const cases = useQuery({
  queryKey: ['cases', 'home'],
  queryFn: () => api.request<Page<CaseItem>>('/cases?limit=6'),
})
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
const metricDays = ref(30)
const metrics = useQuery({
  queryKey: computed(() => ['process-metrics', metricDays.value]),
  queryFn: () => api.request<ProcessMetrics>(`/process-metrics?days=${metricDays.value}`),
})
const maxWait = computed(() =>
  Math.max(
    1,
    ...(metrics.data.value?.steps.map((step) => step.average_wait_hours ?? 0) ?? []),
  ),
)
function countLabel(count: number | undefined, more: boolean | undefined) {
  if (count === undefined) return '—'
  return more ? `${count}+` : String(count)
}
</script>
<template>
  <section class="welcome-section">
    <div>
      <span class="eyebrow">KHÔNG GIAN CỦA BẠN</span>
      <h1>Chào {{ firstName }}, bắt đầu công việc.</h1>
      <p>Những hồ sơ cần bạn xử lý, cùng tài liệu và hoạt động mới nhất.</p>
    </div>
    <div class="date-block"><CalendarDays :size="16" />{{ today }}</div>
  </section>
  <div class="stat-grid">
    <RouterLink to="/approvals" class="stat-tile"
      ><span class="stat-icon"><ClipboardCheck :size="21" /></span>
      <div>
        <strong>{{
          countLabel(
            approvals.data.value?.items.length,
            approvals.data.value?.has_more,
          )
        }}</strong
        ><small>Chờ bạn duyệt</small>
      </div></RouterLink
    ><RouterLink to="/tasks?scope=mine" class="stat-tile"
      ><span class="stat-icon blue"><ListChecks :size="21" /></span>
      <div>
        <strong>{{
          countLabel(myTasks.data.value?.items.length, myTasks.data.value?.has_more)
        }}</strong
        ><small>Việc đang chờ bạn</small>
      </div></RouterLink
    >
    <div class="stat-tile">
      <span class="stat-icon red"><AlarmClock :size="21" /></span>
      <div>
        <strong>{{ metrics.data.value?.overdue_cases ?? '—' }}</strong
        ><small>Hồ sơ quá hạn · {{ metricDays }} ngày</small>
      </div>
    </div>
    <div class="stat-tile">
      <span class="stat-icon amber"><Undo2 :size="21" /></span>
      <div>
        <strong>{{ metrics.data.value?.returns ?? '—' }}</strong
        ><small>Lần trả lại · {{ metricDays }} ngày</small>
      </div>
    </div>
  </div>
  <div class="home-columns">
    <div class="stack">
      <section class="card">
        <header class="card-header">
          <div>
            <span class="eyebrow">VIỆC HÔM NAY</span>
            <h2>Việc của tôi</h2>
          </div>
          <RouterLink to="/tasks?scope=mine" class="button ghost small"
            >Tất cả công việc <ArrowRight :size="15"
          /></RouterLink>
        </header>
        <StatePanel
          :loading="myTasks.isPending.value"
          :error="myTasks.error.value"
          :empty="myTasks.data.value?.items.length === 0"
          title="Không có việc đang chờ bạn"
          description="Việc được giao cho bạn hoặc đơn vị bạn điều phối sẽ xuất hiện tại đây."
          @retry="myTasks.refetch()"
        /><RouterLink
          v-for="task in myTasks.data.value?.items.slice(0, 5)"
          :key="task.id"
          :to="`/tasks/${task.id}`"
          class="list-row"
          style="color: inherit; text-decoration: none"
          ><span class="file-icon"><ListChecks :size="19" /></span>
          <div class="grow">
            <p>{{ task.title }}</p>
            <small
              >{{ task.creator_name }} ·
              <span :class="{ 'overdue-text': task.overdue }">{{
                task.due_at ? `hạn ${formatDate(task.due_at)}` : 'chưa đặt hạn'
              }}</span></small
            >
          </div>
          <StatusBadge :status="task.status"
        /></RouterLink>
      </section>
      <section class="card">
        <header class="card-header">
          <div>
            <span class="eyebrow">ƯU TIÊN XỬ LÝ</span>
            <h2>Hồ sơ cần quyết định</h2>
          </div>
          <RouterLink to="/approvals" class="button ghost small"
            >Xem hộp duyệt <ArrowRight :size="15"
          /></RouterLink>
        </header>
        <StatePanel
          :loading="approvals.isPending.value"
          :error="approvals.error.value"
          :empty="approvals.data.value?.items.length === 0"
          title="Chưa có hồ sơ chờ bạn duyệt"
          description="Khi được phân công, hồ sơ sẽ xuất hiện tại đây cùng bước cần xử lý."
          @retry="approvals.refetch()"
        /><RouterLink
          v-for="task in approvals.data.value?.items.slice(0, 5)"
          :key="task.id"
          :to="`/cases/${task.case_id}`"
          class="list-row"
          style="color: inherit; text-decoration: none"
          ><span class="file-icon"><ClipboardCheck :size="19" /></span>
          <div class="grow">
            <p>{{ task.case_title || task.case_code || 'Hồ sơ cần xử lý' }}</p>
            <small
              >{{ task.label || task.step_label || 'Phê duyệt hồ sơ' }} ·
              {{ formatDate(task.created_at) }}</small
            >
          </div>
          <ArrowRight :size="17" class="muted"
        /></RouterLink>
      </section>
      <section class="card">
        <header class="card-header">
          <div>
            <span class="eyebrow">THEO DÕI TIẾN TRÌNH</span>
            <h2>Hồ sơ gần đây</h2>
          </div>
          <RouterLink to="/cases" class="button ghost small"
            >Tất cả hồ sơ <ArrowRight :size="15"
          /></RouterLink>
        </header>
        <StatePanel
          :loading="cases.isPending.value"
          :error="cases.error.value"
          :empty="cases.data.value?.items.length === 0"
          title="Hồ sơ đầu tiên bắt đầu từ bạn"
          description="Tạo hồ sơ từ mẫu có sẵn, đính kèm tài liệu và chuyển đến người duyệt phù hợp."
          @retry="cases.refetch()"
          ><RouterLink to="/cases?create=1" class="button small"
            >Tạo hồ sơ</RouterLink
          ></StatePanel
        >
        <div
          v-for="item in cases.data.value?.items.slice(0, 6)"
          :key="item.id"
          class="list-row"
        >
          <div class="grow">
            <RouterLink :to="`/cases/${item.id}`" class="row-link">{{
              item.title
            }}</RouterLink
            ><small
              ><span class="mono">{{ item.code }}</span> ·
              {{ formatDate(item.updated_at || item.created_at) }}</small
            >
          </div>
          <StatusBadge :status="item.status" />
        </div>
      </section>
    </div>
    <aside class="stack" style="align-content: start">
      <section class="card">
        <header class="card-header"><h2>Bắt đầu từ đây</h2></header>
        <RouterLink to="/cases?create=1" class="home-launcher"
          ><span><FilePlus2 :size="21" /></span>
          <div>
            <strong>Tạo một hồ sơ</strong
            ><small>Chọn mẫu, điền thông tin, chuyển duyệt</small>
          </div>
          <ArrowRight :size="17" /></RouterLink
        ><RouterLink to="/tasks?create=1" class="home-launcher"
          ><span><ListChecks :size="21" /></span>
          <div>
            <strong>Giao một việc</strong
            ><small>Giao cho người hoặc đơn vị, đặt hạn và checklist</small>
          </div>
          <ArrowRight :size="17" /></RouterLink
        ><RouterLink to="/drive" class="home-launcher"
          ><span><FolderClosed :size="21" /></span>
          <div>
            <strong>Mở kho tài liệu</strong
            ><small>Tải lên, chia sẻ và quản lý phiên bản</small>
          </div>
          <ArrowRight :size="17" /></RouterLink
        ><RouterLink to="/approvals" class="home-launcher"
          ><span><ClipboardCheck :size="21" /></span>
          <div>
            <strong>Xem hộp phê duyệt</strong
            ><small>Kiểm tra và ra quyết định</small>
          </div>
          <ArrowRight :size="17"
        /></RouterLink>
      </section>
      <section class="card">
        <div class="card-body">
          <ShieldCheck
            :size="27"
            style="color: var(--teal); margin-bottom: 15px"
          />
          <h3>Mỗi quyết định có căn cứ</h3>
          <p
            class="muted"
            style="font-size: 14px; line-height: 1.7; margin-top: 10px"
          >
            Hồ sơ khi trình duyệt giữ nguyên bản thông tin và phiên bản tài
            liệu. Chỉnh sửa về sau không làm thay đổi nội dung đã trình.
          </p>
          <div class="date-line" style="margin-top: 20px">
            <History :size="15" /> Lịch sử được giữ theo từng lần trình
          </div>
        </div>
      </section>
    </aside>
  </div>
  <div class="intro-strip">
    <ShieldCheck :size="24" />
    <p>
      <strong>Quyền truy cập đi cùng dữ liệu.</strong> Bạn chỉ nhìn thấy hồ sơ,
      tài liệu và nhiệm vụ được cấp quyền. Các danh sách được lấy trực tiếp từ
      hệ thống.
    </p>
  </div>
  <section class="card" style="margin-top: 20px">
    <header class="card-header">
      <div><span class="eyebrow">CẢI TIẾN QUY TRÌNH</span><h2>Thời gian chờ theo bước</h2></div>
      <label class="period-select">Khoảng thời gian <select v-model.number="metricDays"><option :value="7">7 ngày</option><option :value="30">30 ngày</option><option :value="90">90 ngày</option></select></label>
    </header>
    <div class="card-body">
      <StatePanel :loading="metrics.isPending.value" :error="metrics.error.value"
        :empty="metrics.data.value?.sample_size === 0" title="Chưa có nhiệm vụ đủ dữ liệu thời gian"
        @retry="metrics.refetch()" />
      <template v-if="metrics.data.value?.sample_size">
        <p class="muted" style="font-size: 13px">{{ metrics.data.value.sample_size }} nhiệm vụ · cập nhật {{ formatDate(metrics.data.value.as_of, true) }}<span v-if="metrics.data.value.truncated"> · giới hạn 2.000 mẫu mới nhất</span></p>
        <div v-for="step in metrics.data.value.steps" :key="`${step.package_version_id}:${step.step}`" class="metric-row">
          <div><strong>{{ step.step }}</strong><small v-if="step.package_version_id">Gói {{ step.package_version_id.slice(0, 8) }}</small><small>{{ step.count }} lượt · {{ step.waiting }} đang chờ</small>
            <div v-if="step.case_ids.length" class="metric-cases"><RouterLink v-for="caseId in step.case_ids" :key="caseId" :to="`/cases/${caseId}`" class="mono">Hồ sơ {{ caseId.slice(0, 8) }}</RouterLink></div>
          </div>
          <div>
            <div class="metric-bar" aria-hidden="true"><span :style="{ width: `${((step.average_wait_hours ?? 0) / maxWait) * 100}%` }" /></div>
            <span class="metric-bar-label">Trung bình {{ step.average_wait_hours === null ? 'chưa có' : `${step.average_wait_hours} giờ` }}</span>
          </div>
        </div>
        <div v-if="metrics.data.value.suggestions.length" class="notice" style="margin-top: 18px">
          <strong>Điểm cần kiểm tra</strong>
          <p v-for="suggestion in metrics.data.value.suggestions" :key="`${suggestion.kind}:${suggestion.step}`">{{ suggestion.step ? `${suggestion.step}: ` : '' }}{{ suggestion.message }} ({{ suggestion.sample_size }} mẫu)</p>
        </div>
      </template>
    </div>
  </section>
</template>
