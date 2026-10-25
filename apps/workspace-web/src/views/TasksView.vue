<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import {
  AlarmClock,
  CalendarClock,
  ChevronRight,
  Columns3,
  List,
  ListChecks,
  Plus,
  Search,
} from 'lucide-vue-next'
import { api } from '../api'
import { formatDate, queryString } from '@dx/web-shared/api.ts'
import type { Page } from '@dx/web-shared/api.ts'
import type { Task, TaskStatus } from '@dx/web-shared/types.ts'
import StatePanel from '@dx/web-shared/components/StatePanel.vue'
import StatusBadge from '@dx/web-shared/components/StatusBadge.vue'
import TaskCreateDialog from '../components/TaskCreateDialog.vue'
const route = useRoute()
const router = useRouter()
const queryClient = useQueryClient()
type Scope = 'mine' | 'created' | 'watching' | 'managed' | 'all'
const scope = ref<Scope>((route.query.scope as Scope) || 'mine')
const status = ref(String(route.query.status ?? ''))
const overdueOnly = ref(route.query.overdue === 'true')
const search = ref('')
const view = ref<'list' | 'board' | 'due'>('list')
const cursor = ref<string | null>(null)
const showCreate = ref(route.query.create === '1')
watch(
  () => route.query.create,
  (value) => {
    if (value) showCreate.value = true
  },
)
watch([scope, status, search, overdueOnly], () => (cursor.value = null))
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
const columns: { status: TaskStatus; label: string }[] = [
  { status: 'assigned', label: 'Chờ tiếp nhận' },
  { status: 'accepted', label: 'Đã tiếp nhận' },
  { status: 'in_progress', label: 'Đang làm' },
  { status: 'blocked', label: 'Vướng mắc' },
  { status: 'returned', label: 'Bị trả lại' },
  { status: 'submitted', label: 'Chờ nghiệm thu' },
  { status: 'completed', label: 'Hoàn tất' },
]
const priorityLabel = { low: 'Thấp', normal: 'Bình thường', high: 'Cao', urgent: 'Khẩn' }
function bucket(task: Task) {
  if (['completed', 'cancelled'].includes(task.status)) return 'done'
  if (!task.due_at) return 'none'
  if (task.overdue) return 'overdue'
  const due = new Date(task.due_at)
  const now = new Date()
  const end = new Date(now)
  end.setHours(23, 59, 59, 999)
  if (due <= end) return 'today'
  end.setDate(end.getDate() + 7)
  return due <= end ? 'week' : 'later'
}
const dueGroups = computed(() =>
  [
    { key: 'overdue', label: 'Quá hạn' },
    { key: 'today', label: 'Hạn hôm nay' },
    { key: 'week', label: 'Trong 7 ngày tới' },
    { key: 'later', label: 'Sau đó' },
    { key: 'none', label: 'Chưa đặt hạn' },
  ].map((group) => ({
    ...group,
    tasks: items.value
      .filter((task) => bucket(task) === group.key)
      .sort((a, b) => (a.due_at ?? '').localeCompare(b.due_at ?? '')),
  })),
)
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
  <header class="page-head">
    <div>
      <span class="eyebrow">ĐIỀU HÀNH CÔNG VIỆC</span>
      <h1>Công việc</h1>
      <p>Giao việc theo cấp quản lý, theo dõi tiến độ và nghiệm thu kết quả.</p>
    </div>
    <div class="page-actions">
      <button class="button" @click="showCreate = true">
        <Plus :size="18" />Giao việc
      </button>
    </div>
  </header>
  <section class="card">
    <div class="toolbar">
      <div class="tabs">
        <button
          v-for="tab in [
            { value: 'mine', label: 'Việc của tôi' },
            { value: 'created', label: 'Tôi đã giao' },
            { value: 'watching', label: 'Đang theo dõi' },
            { value: 'managed', label: 'Tôi điều phối' },
            { value: 'all', label: 'Tất cả' },
          ] as const"
          :key="tab.value"
          class="tab"
          :class="{ active: scope === tab.value }"
          @click="scope = tab.value"
        >
          {{ tab.label }}
        </button>
      </div>
      <div class="inline-actions">
        <select v-model="status" aria-label="Lọc trạng thái" class="compact-select">
          <option value="">Mọi trạng thái</option>
          <option value="assigned,accepted,in_progress,blocked,returned,submitted">
            Đang mở
          </option>
          <option v-for="column in columns" :key="column.status" :value="column.status">
            {{ column.label }}
          </option>
          <option value="draft">Bản nháp</option>
          <option value="cancelled">Đã hủy</option>
        </select>
        <label class="checkbox-label" style="margin: 0"
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
            :class="{ active: view === 'list' }"
            aria-label="Danh sách"
            title="Danh sách"
            @click="view = 'list'"
          >
            <List :size="17" /></button
          ><button
            :class="{ active: view === 'board' }"
            aria-label="Kanban"
            title="Kanban"
            @click="view = 'board'"
          >
            <Columns3 :size="17" /></button
          ><button
            :class="{ active: view === 'due' }"
            aria-label="Theo hạn"
            title="Theo hạn"
            @click="view = 'due'"
          >
            <CalendarClock :size="17" />
          </button>
        </div>
      </div>
    </div>
    <StatePanel
      :loading="tasks.isPending.value"
      :error="tasks.error.value"
      :empty="items.length === 0"
      :title="scope === 'mine' ? 'Bạn chưa có việc được giao' : 'Chưa có công việc phù hợp'"
      description="Công việc được giao cho bạn hoặc đơn vị bạn điều phối sẽ xuất hiện tại đây."
      @retry="tasks.refetch()"
      ><button class="button small" @click="showCreate = true">
        <Plus :size="16" />Giao việc
      </button></StatePanel
    >
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
                  <RouterLink :to="`/tasks/${task.id}`" class="row-link">{{
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
            <td :class="task.overdue ? 'overdue-text' : 'muted'">
              <AlarmClock v-if="task.overdue" :size="14" />
              {{ formatDate(task.due_at, true) }}
            </td>
            <td>
              <span class="priority" :class="`priority-${task.priority}`">{{
                priorityLabel[task.priority]
              }}</span>
            </td>
            <td><StatusBadge :status="task.status" /></td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-if="items.length && view === 'board'" class="kanban">
      <div v-for="column in columns" :key="column.status" class="kanban-column">
        <header>
          <StatusBadge :status="column.status" /><span class="muted">{{
            items.filter((task) => task.status === column.status).length
          }}</span>
        </header>
        <RouterLink
          v-for="task in items.filter((item) => item.status === column.status)"
          :key="task.id"
          :to="`/tasks/${task.id}`"
          class="kanban-card"
          :class="{ overdue: task.overdue }"
        >
          <strong>{{ task.title }}</strong>
          <small>{{ task.assignee_name || task.department_name || 'Chưa giao' }}</small>
          <div class="kanban-meta">
            <span class="priority" :class="`priority-${task.priority}`">{{
              priorityLabel[task.priority]
            }}</span>
            <span v-if="task.due_at" :class="{ 'overdue-text': task.overdue }">{{
              formatDate(task.due_at)
            }}</span>
          </div>
        </RouterLink>
      </div>
    </div>
    <div v-if="items.length && view === 'due'" class="due-groups">
      <section v-for="group in dueGroups.filter((g) => g.tasks.length)" :key="group.key">
        <h3 :class="{ 'overdue-text': group.key === 'overdue' }">
          {{ group.label }} <span class="muted">· {{ group.tasks.length }}</span>
        </h3>
        <RouterLink
          v-for="task in group.tasks"
          :key="task.id"
          :to="`/tasks/${task.id}`"
          class="list-row"
          style="color: inherit; text-decoration: none"
        >
          <div class="grow">
            <p>{{ task.title }}</p>
            <small
              >{{ task.assignee_name || task.department_name || 'Chưa giao' }} ·
              {{ formatDate(task.due_at, true) }}</small
            >
          </div>
          <StatusBadge :status="task.status" />
        </RouterLink>
      </section>
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
  <TaskCreateDialog v-if="showCreate" @close="closeCreate" @created="created" />
</template>
