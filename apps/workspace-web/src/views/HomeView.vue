<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import {
  AlarmClock,
  ArrowRight,
  AtSign,
  CalendarDays,
  Check,
  ClipboardCheck,
  Eye,
  FilePlus2,
  FolderClosed,
  ListChecks,
  MessagesSquare,
  PartyPopper,
  UserPlus,
} from 'lucide-vue-next'
import { api } from '../api'
import { useSession } from '../stores/session'
import { useOverview } from '../ui/overview'
import { toast } from '../ui/toast'
import type { Page } from '@dx/web-shared/api.ts'
import { formatDate } from '@dx/web-shared/api.ts'
import type { AgendaItem, CaseItem, Task } from '@dx/web-shared/types.ts'
import StatePanel from '@dx/web-shared/components/StatePanel.vue'
import StatusBadge from '@dx/web-shared/components/StatusBadge.vue'
const session = useSession()
const router = useRouter()
const queryClient = useQueryClient()
const today = new Intl.DateTimeFormat('vi-VN', {
  weekday: 'long',
  day: 'numeric',
  month: 'long',
  year: 'numeric',
}).format(new Date())
const firstName = computed(
  () => session.user?.display_name.split(' ').slice(-1)[0] ?? '',
)
const overview = useOverview()
const counts = computed(() => overview.data.value?.counts)
const agenda = computed(() => overview.data.value?.agenda ?? [])
const overdueCount = computed(() => agenda.value.filter((item) => item.overdue).length)

type Filter = 'all' | 'overdue' | 'task' | 'approval' | 'mention'
const filter = ref<Filter>('all')
const FILTERS: { key: Filter; label: string }[] = [
  { key: 'all', label: 'Tất cả' },
  { key: 'overdue', label: 'Quá hạn' },
  { key: 'task', label: 'Công việc' },
  { key: 'approval', label: 'Phê duyệt' },
  { key: 'mention', label: 'Nhắc đến tôi' },
]
function filterCount(key: Filter) {
  if (key === 'all') return agenda.value.length
  if (key === 'overdue') return overdueCount.value
  return agenda.value.filter((item) => item.kind === key).length
}
const shown = computed(() =>
  agenda.value.filter((item) =>
    filter.value === 'all' ? true : filter.value === 'overdue' ? item.overdue : item.kind === filter.value,
  ),
)
const groups = computed(() => {
  const end = new Date()
  end.setHours(23, 59, 59, 999)
  const buckets: { key: string; label: string; items: AgendaItem[] }[] = [
    { key: 'overdue', label: 'Quá hạn', items: [] },
    { key: 'today', label: 'Hạn hôm nay', items: [] },
    { key: 'later', label: 'Sắp tới', items: [] },
    { key: 'none', label: 'Không đặt hạn', items: [] },
  ]
  for (const item of shown.value) {
    const index = item.overdue ? 0 : !item.due_at ? 3 : new Date(item.due_at) <= end ? 1 : 2
    buckets[index].items.push(item)
  }
  return buckets.filter((bucket) => bucket.items.length)
})

const ACTIONS: Record<AgendaItem['action'], { label: string; icon: typeof Check }> = {
  accept: { label: 'Nhận việc', icon: Check },
  assign: { label: 'Phân công', icon: UserPlus },
  review: { label: 'Xem kết quả', icon: Eye },
  decide: { label: 'Xem và duyệt', icon: ClipboardCheck },
  open: { label: 'Mở', icon: ArrowRight },
}
const KIND_ICONS = { task: ListChecks, approval: ClipboardCheck, mention: AtSign }
const busyId = ref('')
async function act(item: AgendaItem) {
  if (item.action !== 'accept') {
    await router.push(item.link)
    return
  }
  busyId.value = item.id
  try {
    const task = await api.request<Task>(`/tasks/${item.id}`)
    await api.request(`/tasks/${item.id}/transitions`, {
      method: 'POST',
      body: JSON.stringify({ expected_revision: task.revision, action: 'accept', reason: '', result: null }),
    })
    toast.success(`Đã nhận việc “${item.title}”`, {
      label: 'Mở việc',
      run: () => router.push(item.link),
    })
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['me-overview'] }),
      queryClient.invalidateQueries({ queryKey: ['tasks'] }),
    ])
  } catch (error) {
    toast.error(error)
  } finally {
    busyId.value = ''
  }
}
function dueText(item: AgendaItem) {
  if (!item.due_at) return ''
  const due = new Date(item.due_at)
  const days = Math.round((due.getTime() - Date.now()) / 86_400_000)
  if (item.overdue) return days <= -1 ? `quá hạn ${-days} ngày` : 'quá hạn'
  return `hạn ${formatDate(item.due_at, days < 2)}`
}

const cases = useQuery({
  queryKey: ['cases', 'home'],
  queryFn: () => api.request<Page<CaseItem>>('/cases?limit=5'),
})
const canSeeMetrics = computed(
  () => session.can('cases.read.department') || session.can('cases.read.organization'),
)
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
  enabled: canSeeMetrics,
})
const maxWait = computed(() =>
  Math.max(
    1,
    ...(metrics.data.value?.steps.map((step) => step.average_wait_hours ?? 0) ?? []),
  ),
)
const summary = computed(() => {
  if (!overview.data.value) return 'Đang xem những việc cần bạn hôm nay…'
  const total = agenda.value.length
  if (!total) return 'Không có việc nào đang chờ bạn. Một ngày nhẹ nhàng!'
  return overdueCount.value
    ? `Bạn có ${total} việc cần xử lý, trong đó ${overdueCount.value} việc đã quá hạn.`
    : `Bạn có ${total} việc cần xử lý. Chưa có việc nào quá hạn.`
})
</script>
<template>
  <section class="welcome-section">
    <div>
      <span class="eyebrow">VIỆC HÔM NAY</span>
      <h1>Chào {{ firstName }}!</h1>
      <p>{{ summary }}</p>
    </div>
    <div class="date-block"><CalendarDays :size="16" />{{ today }}</div>
  </section>
  <div class="stat-grid">
    <RouterLink to="/tasks?scope=mine" class="stat-tile"
      ><span class="stat-icon blue"><ListChecks :size="21" /></span>
      <div>
        <strong>{{ counts?.tasks ?? '—' }}</strong><small>Việc đang chờ bạn</small>
      </div></RouterLink
    ><RouterLink to="/tasks?scope=managed&status=submitted" class="stat-tile"
      ><span class="stat-icon amber"><Eye :size="21" /></span>
      <div>
        <strong>{{ counts?.tasks_to_review ?? '—' }}</strong><small>Kết quả cần xem</small>
      </div></RouterLink
    ><RouterLink to="/approvals" class="stat-tile"
      ><span class="stat-icon"><ClipboardCheck :size="21" /></span>
      <div>
        <strong>{{ counts?.approvals ?? '—' }}</strong><small>Hồ sơ chờ bạn duyệt</small>
      </div></RouterLink
    ><RouterLink to="/chat" class="stat-tile"
      ><span class="stat-icon red"><MessagesSquare :size="21" /></span>
      <div>
        <strong>{{ counts?.chat ?? '—' }}</strong><small>Tin nhắn chưa đọc</small>
      </div></RouterLink
    >
  </div>
  <div class="home-columns">
    <section class="card agenda-card" data-tour="agenda">
      <header class="card-header">
        <div>
          <span class="eyebrow">MỘT DANH SÁCH CHO MỌI VIỆC</span>
          <h2>Việc cần làm hôm nay</h2>
        </div>
        <span v-if="overdueCount" class="overdue-pill"><AlarmClock :size="14" />{{ overdueCount }} quá hạn</span>
      </header>
      <div class="chip-row agenda-filters" role="group" aria-label="Lọc việc">
        <button
          v-for="item in FILTERS"
          :key="item.key"
          type="button"
          class="chip"
          :class="{ active: filter === item.key }"
          :aria-pressed="filter === item.key"
          @click="filter = item.key"
        >
          {{ item.label }}<span class="chip-count">{{ filterCount(item.key) }}</span>
        </button>
      </div>
      <StatePanel
        :loading="overview.isPending.value"
        :error="overview.error.value"
        :rows="4"
        @retry="overview.refetch()"
      />
      <div v-if="overview.data.value && !shown.length" class="state-panel agenda-done">
        <span class="state-illustration" aria-hidden="true"><PartyPopper :size="28" /></span>
        <strong>{{ filter === 'all' ? 'Bạn đã xong mọi việc đang chờ' : 'Không có việc trong mục này' }}</strong>
        <span>Việc mới được giao, hồ sơ cần duyệt và lời nhắc sẽ hiện ở đây.</span>
        <RouterLink v-if="session.can('tasks.create')" to="/tasks?create=1" class="button small secondary">Giao một việc</RouterLink>
      </div>
      <div v-for="group in groups" :key="group.key" class="agenda-group">
        <h3 :class="{ danger: group.key === 'overdue' }">{{ group.label }} <span>{{ group.items.length }}</span></h3>
        <div v-for="item in group.items" :key="`${item.kind}:${item.id}`" class="agenda-row" :class="{ overdue: item.overdue }">
          <span class="agenda-icon" :class="item.kind"><component :is="KIND_ICONS[item.kind]" :size="17" /></span>
          <RouterLink :to="item.link" class="agenda-main">
            <strong>{{ item.title }}</strong>
            <small
              >{{ item.detail }}<template v-if="item.due_at"> · <span :class="{ 'overdue-text': item.overdue }">{{ dueText(item) }}</span></template></small
            >
          </RouterLink>
          <StatusBadge v-if="item.kind === 'task' && item.status" :status="item.status" class="agenda-status" />
          <button
            type="button"
            class="button small"
            :class="{ secondary: item.action === 'open' }"
            :disabled="busyId === item.id"
            :aria-label="`${ACTIONS[item.action].label}: ${item.title}`"
            @click="act(item)"
          >
            <component :is="ACTIONS[item.action].icon" :size="15" />{{ ACTIONS[item.action].label }}
          </button>
        </div>
      </div>
    </section>
    <aside class="stack" style="align-content: start">
      <section class="card">
        <header class="card-header"><h2>Bắt đầu nhanh</h2></header>
        <RouterLink v-if="session.can('tasks.create')" to="/tasks?create=1" class="home-launcher"
          ><span><ListChecks :size="21" /></span>
          <div>
            <strong>Giao một việc</strong
            ><small>Cho người hoặc phòng, đặt hạn và danh sách kiểm</small>
          </div>
          <ArrowRight :size="17" /></RouterLink
        ><RouterLink v-if="session.can('cases.create')" to="/cases?create=1" class="home-launcher"
          ><span><FilePlus2 :size="21" /></span>
          <div>
            <strong>Lập hồ sơ trình duyệt</strong
            ><small>Chọn mẫu, điền thông tin, gửi người duyệt</small>
          </div>
          <ArrowRight :size="17" /></RouterLink
        ><RouterLink to="/drive" class="home-launcher"
          ><span><FolderClosed :size="21" /></span>
          <div>
            <strong>Mở kho tài liệu</strong
            ><small>Tải lên, chia sẻ và soạn thảo cùng nhau</small>
          </div>
          <ArrowRight :size="17"
        /></RouterLink>
      </section>
      <section class="card">
        <header class="card-header">
          <h2>Hồ sơ gần đây</h2>
          <RouterLink to="/cases" class="button ghost small">Tất cả <ArrowRight :size="15" /></RouterLink>
        </header>
        <StatePanel
          :loading="cases.isPending.value"
          :error="cases.error.value"
          :empty="cases.data.value?.items.length === 0"
          compact
          title="Chưa có hồ sơ nào"
          description="Hồ sơ bạn lập hoặc được xem sẽ hiện ở đây."
          @retry="cases.refetch()"
        />
        <div v-for="item in cases.data.value?.items" :key="item.id" class="list-row">
          <div class="grow">
            <RouterLink :to="`/cases/${item.id}`" class="row-link">{{ item.title }}</RouterLink
            ><small>{{ formatDate(item.updated_at || item.created_at) }}</small>
          </div>
          <StatusBadge :status="item.status" />
        </div>
      </section>
    </aside>
  </div>
  <section v-if="canSeeMetrics" class="card" style="margin-top: 20px">
    <header class="card-header">
      <div><span class="eyebrow">CẢI TIẾN QUY TRÌNH</span><h2>Hồ sơ đang chờ lâu ở bước nào?</h2></div>
      <label class="period-select">Trong <select v-model.number="metricDays"><option :value="7">7 ngày</option><option :value="30">30 ngày</option><option :value="90">90 ngày</option></select></label>
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
