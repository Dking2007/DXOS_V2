<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import {
  AlarmClock,
  ChevronRight,
  List,
  ListChecks,
  Plus,
  Search,
  StickyNote,
} from 'lucide-vue-next'
import { api } from '../api'
import { formatDate, queryString } from '@dx/web-shared/api.ts'
import type { Page } from '@dx/web-shared/api.ts'
import type { Task, TaskStatus } from '@dx/web-shared/types.ts'
import StatePanel from '@dx/web-shared/components/StatePanel.vue'
import StatusBadge from '@dx/web-shared/components/StatusBadge.vue'
import TaskCreateDialog from '../components/TaskCreateDialog.vue'
import TaskPaper from '../components/TaskPaper.vue'
import { useOverview } from '../ui/overview'
import { useSession } from '../stores/session'
const route = useRoute()
const router = useRouter()
const queryClient = useQueryClient()
const session = useSession()
// Only people allowed to create tasks see the button; the server refuses the others anyway.
const canCreate = computed(() => session.can('tasks.create'))
type Scope = 'mine' | 'review' | 'created' | 'watching' | 'managed' | 'all'
const scope = ref<Scope>((route.query.scope as Scope) || 'mine')
// The menu badge counts work to do plus results to accept; each has its own tab with its count,
// and the page opens on the tab that actually holds what the badge announced.
const overview = useOverview()
const counts = computed(() => overview.data.value?.counts)
let chosen = !!route.query.scope
watch(
  counts,
  (value) => {
    if (chosen || !value) return
    chosen = true
    if (!value.tasks && value.tasks_to_review) scope.value = 'review'
  },
  { immediate: true },
)
const tabs = computed(() => [
  { value: 'mine' as const, label: 'Việc của tôi', count: counts.value?.tasks ?? 0 },
  { value: 'review' as const, label: 'Chờ tôi nghiệm thu', count: counts.value?.tasks_to_review ?? 0 },
  { value: 'created' as const, label: 'Tôi đã giao', count: 0 },
  { value: 'watching' as const, label: 'Đang theo dõi', count: 0 },
  { value: 'managed' as const, label: 'Tôi điều phối', count: 0 },
  { value: 'all' as const, label: 'Tất cả', count: 0 },
])
function pick(value: Scope) {
  chosen = true
  scope.value = value
}
const status = ref(String(route.query.status ?? ''))
const overdueOnly = ref(route.query.overdue === 'true')
const search = ref('')
// Sheets of paper by default; each person's own choice of view is remembered on this browser.
type View = 'paper' | 'list'
const VIEW_KEY = 'dx-tasks-view'
function storedView(): View {
  try {
    const saved = window.localStorage.getItem(VIEW_KEY)
    return saved === 'list' ? 'list' : 'paper'
  } catch {
    return 'paper'
  }
}
const view = ref<View>(storedView())
watch(view, (value) => {
  try {
    window.localStorage.setItem(VIEW_KEY, value)
  } catch {
    // Storage blocked: the choice lasts for this visit only.
  }
})
const cursor = ref<string | null>(null)
const showCreate = ref(route.query.create === '1')
watch(
  () => route.query.create,
  (value) => {
    if (value) showCreate.value = true
  },
)
watch([scope, status, search, overdueOnly], () => (cursor.value = null))
const filtered = computed(() => !!status.value || !!search.value || overdueOnly.value)
function clearFilters() {
  status.value = ''
  search.value = ''
  overdueOnly.value = false
}
const tasks = useQuery({
  queryKey: computed(() => [
    'tasks',
    scope.value,
    status.value,
    search.value,
    overdueOnly.value,
    cursor.value,
  ]),
  queryFn: () =>
    api.request<Page<Task>>(
      `/tasks${queryString({
        scope: scope.value,
        status: status.value,
        q: search.value,
        overdue: overdueOnly.value ? true : undefined,
        cursor: cursor.value,
        limit: 200,
      })}`,
    ),
})
const items = computed(() => tasks.data.value?.items ?? [])
const statuses: { status: TaskStatus; label: string }[] = [
  { status: 'assigned', label: 'Chờ tiếp nhận' },
  { status: 'accepted', label: 'Đã tiếp nhận' },
  { status: 'in_progress', label: 'Đang thực hiện' },
  { status: 'blocked', label: 'Vướng mắc' },
  { status: 'returned', label: 'Bị trả lại' },
  { status: 'submitted', label: 'Chờ nghiệm thu' },
  { status: 'completed', label: 'Hoàn tất' },
]
const priorityLabel = { low: 'Thấp', normal: 'Bình thường', high: 'Cao', urgent: 'Khẩn' }
async function created(task: Task) {
  showCreate.value = false
  await queryClient.invalidateQueries({ queryKey: ['tasks'] })
  await router.push(`/tasks/${task.id}`)
}
function closeCreate() {
  showCreate.value = false
  if (route.query.create) router.replace('/tasks')
}
</script>
<template>
  <header class="page-head compact">
    <h1 class="sr-only">Công việc</h1>
    <div v-if="canCreate" class="page-actions">
      <button class="button" @click="showCreate = true">
        <Plus :size="18" />Giao việc
      </button>
    </div>
  </header>
  <section class="card">
    <div class="toolbar">
      <div class="tabs">
        <button
          v-for="tab in tabs.filter((t) => t.value !== 'review' || t.count || scope === 'review')"
          :key="tab.value"
          class="tab"
          :class="{ active: scope === tab.value }"
          @click="pick(tab.value)"
        >
          {{ tab.label }}<span v-if="tab.count" class="tab-count">{{ tab.count }}</span>
        </button>
      </div>
      <div class="inline-actions">
        <select v-model="status" aria-label="Lọc trạng thái" class="compact-select">
          <option value="">Mọi trạng thái</option>
          <option value="assigned,accepted,in_progress,blocked,returned,submitted">
            Đang mở
          </option>
          <option v-for="item in statuses" :key="item.status" :value="item.status">
            {{ item.label }}
          </option>
          <option value="draft">Bản nháp</option>
          <option value="cancelled">Đã hủy</option>
        </select>
        <label class="checkbox-label tasks-overdue-toggle"
          ><input v-model="overdueOnly" type="checkbox" />Quá hạn</label
        >
        <label class="search-box"
          ><Search :size="17" /><input
            v-model.lazy="search"
            type="search"
            placeholder="Tìm công việc…"
            aria-label="Tìm công việc"
        /></label>
        <div class="segmented" role="group" aria-label="Kiểu hiển thị">
          <button
            :class="{ active: view === 'paper' }"
            :aria-pressed="view === 'paper'"
            aria-label="Dạng giấy"
            title="Dạng giấy"
            @click="view = 'paper'"
          >
            <StickyNote :size="17" /></button
          ><button
            :class="{ active: view === 'list' }"
            :aria-pressed="view === 'list'"
            aria-label="Danh sách"
            title="Danh sách"
            @click="view = 'list'"
          >
            <List :size="17" />
          </button>
        </div>
      </div>
    </div>
    <StatePanel
      :loading="tasks.isPending.value"
      :error="tasks.error.value"
      :empty="items.length === 0"
      :title="
        filtered
          ? 'Không có công việc khớp bộ lọc'
          : scope === 'mine'
            ? 'Bạn chưa có việc được giao'
            : scope === 'review'
              ? 'Không có kết quả nào chờ bạn nghiệm thu'
              : 'Chưa có công việc phù hợp'
      "
      :description="
        filtered
          ? 'Thử bỏ bớt bộ lọc trạng thái, quá hạn hoặc từ khóa tìm kiếm.'
          : 'Công việc được giao cho bạn hoặc đơn vị bạn điều phối sẽ xuất hiện tại đây.'
      "
      @retry="tasks.refetch()"
      ><button v-if="filtered" class="button small secondary" @click="clearFilters">
        Xóa bộ lọc</button
      ><button v-else-if="canCreate" class="button small" @click="showCreate = true">
        <Plus :size="16" />Giao việc
      </button></StatePanel
    >
    <div v-if="items.length && view === 'paper'" class="paper-board">
      <TaskPaper v-for="task in items" :key="task.id" :task="task" />
    </div>
    <div v-if="items.length && view === 'list'" class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Công việc</th>
            <th>Người nhận</th>
            <th>Hạn</th>
            <th>Ưu tiên</th>
            <th>Trạng thái</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="task in items" :key="task.id">
            <td>
              <div class="primary-cell">
                <span class="file-icon"><ListChecks :size="19" /></span>
                <div>
                  <RouterLink :to="`/tasks/${task.id}`" class="row-link task-title" :title="task.title">{{
                    task.title
                  }}</RouterLink
                  ><small
                    >Giao bởi {{ task.creator_name
                    }}<template v-if="task.checklist_total">
                      · {{ task.checklist_done }}/{{ task.checklist_total }} mục</template
                    ></small
                  >
                </div>
              </div>
            </td>
            <td>
              {{ task.assignee_name || task.department_name || '—' }}
              <small v-if="!task.assignee_id && task.department_id" class="muted"
                >(chờ phân công)</small
              >
            </td>
            <td class="nowrap" :class="task.overdue ? 'overdue-text' : 'muted'">
              <AlarmClock v-if="task.overdue" :size="14" />
              {{ task.due_at ? formatDate(task.due_at, true) : '—' }}
            </td>
            <td>
              <span class="priority" :class="`priority-${task.priority}`">{{
                priorityLabel[task.priority]
              }}</span>
            </td>
            <td><StatusBadge kind="task" :status="task.status" /></td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-if="tasks.data.value?.has_more || cursor" class="pagination">
      <button class="button secondary small" :disabled="!cursor" @click="cursor = null">
        Về đầu</button
      ><button
        class="button secondary small"
        :disabled="!tasks.data.value?.has_more"
        @click="cursor = tasks.data.value?.next_cursor ?? null"
      >
        Trang tiếp <ChevronRight :size="15" />
      </button>
    </div>
  </section>
  <TaskCreateDialog v-if="showCreate && canCreate" @close="closeCreate" @created="created" />
</template>
<style scoped>
/* A cork-board of sheets: enough room around each one for its tilt and its tape. */
.paper-board {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 30px 26px;
  padding: 30px var(--space-6, 24px) 28px;
  border-top: 1px solid var(--border);
  background-color: var(--surface-2);
  background-image: radial-gradient(color-mix(in srgb, var(--border) 70%, transparent) 1px, transparent 1px);
  background-size: 16px 16px;
  border-radius: 0 0 8px 8px;
}
.tasks-overdue-toggle {
  margin: 0;
  min-height: 36px;
  gap: 8px;
}
.task-title {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  overflow-wrap: anywhere;
}
.nowrap {
  white-space: nowrap;
}
</style>
