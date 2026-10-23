<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { AtSign, Bell, Bot, CheckCheck, ClipboardCheck, ListChecks, Newspaper } from 'lucide-vue-next'
import type { Notification } from '@dx/web-shared/types.ts'
import type { Page } from '@dx/web-shared/api.ts'
import { formatDate } from '@dx/web-shared/api.ts'
import StatePanel from '@dx/web-shared/components/StatePanel.vue'
import { api } from '../../api'
import { useSession } from '../../stores/session'
import { useDismiss } from '../../ui/popover'
import { toast } from '../../ui/toast'

const session = useSession()
const router = useRouter()
const queryClient = useQueryClient()
const open = ref(false)
const root = ref<HTMLElement>()
const trigger = ref<HTMLButtonElement>()
useDismiss(root, open, trigger)

type Category = NonNullable<Notification['category']>
const FILTERS: { key: 'all' | 'unread' | Category; label: string }[] = [
  { key: 'all', label: 'Tất cả' },
  { key: 'unread', label: 'Chưa đọc' },
  { key: 'approval', label: 'Phê duyệt' },
  { key: 'task', label: 'Công việc' },
  { key: 'mention', label: 'Nhắc đến' },
  { key: 'feed', label: 'Bảng tin' },
]
const ICONS = { approval: ClipboardCheck, task: ListChecks, mention: AtSign, feed: Newspaper, automation: Bot, other: Bell }
const filter = ref<(typeof FILTERS)[number]['key']>('all')

const notifications = useQuery({
  queryKey: ['notifications'],
  queryFn: () => api.request<Page<Notification>>('/notifications'),
  enabled: computed(() => !!session.user),
  refetchInterval: 60_000,
})
const items = computed(() => notifications.data.value?.items ?? [])
const unreadCount = computed(() => items.value.filter((item) => !item.read_at).length)
const shown = computed(() =>
  items.value.filter((item) =>
    filter.value === 'all' ? true : filter.value === 'unread' ? !item.read_at : item.category === filter.value,
  ),
)
const groups = computed(() => {
  const start = new Date()
  start.setHours(0, 0, 0, 0)
  const today = shown.value.filter((item) => new Date(item.created_at) >= start)
  const earlier = shown.value.filter((item) => new Date(item.created_at) < start)
  return [
    { label: 'Hôm nay', items: today },
    { label: 'Trước đó', items: earlier },
  ].filter((group) => group.items.length)
})

async function refresh() {
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: ['notifications'] }),
    queryClient.invalidateQueries({ queryKey: ['me-overview'] }),
  ])
}
async function markRead(item: Notification) {
  await api.request(`/notifications/${item.id}`, { method: 'PATCH', body: JSON.stringify({}) })
  await refresh()
}
async function markAll() {
  try {
    const result = await api.request<{ updated: number }>('/notifications/read-all', { method: 'POST' })
    await refresh()
    toast.success(result.updated ? `Đã đánh dấu ${result.updated} thông báo là đã đọc` : 'Không còn thông báo chưa đọc')
  } catch (error) {
    toast.error(error)
  }
}
async function openItem(item: Notification) {
  try {
    if (!item.read_at) await markRead(item)
  } catch (error) {
    toast.error(error)
  }
  if (item.link) {
    open.value = false
    await router.push(item.link)
  }
}
</script>
<template>
  <div ref="root" class="notification-menu">
    <button
      ref="trigger"
      class="icon-button notification-button"
      type="button"
      :aria-label="unreadCount ? `Thông báo, ${unreadCount} chưa đọc` : 'Thông báo'"
      aria-haspopup="dialog"
      :aria-expanded="open"
      @click="open = !open"
    >
      <Bell :size="20" /><i v-if="unreadCount" class="count-dot">{{ unreadCount > 9 ? '9+' : unreadCount }}</i>
    </button>
    <section v-if="open" class="dropdown notification-panel" role="dialog" aria-label="Thông báo">
      <header class="notification-panel-head">
        <strong>Thông báo</strong>
        <button v-if="unreadCount" class="link-button" type="button" @click="markAll">
          <CheckCheck :size="15" />Đánh dấu tất cả đã đọc
        </button>
      </header>
      <div class="chip-row" role="group" aria-label="Lọc thông báo">
        <button
          v-for="item in FILTERS"
          :key="item.key"
          type="button"
          class="chip"
          :class="{ active: filter === item.key }"
          :aria-pressed="filter === item.key"
          @click="filter = item.key"
        >
          {{ item.label }}
        </button>
      </div>
      <div class="notification-scroll">
        <StatePanel
          :loading="notifications.isPending.value"
          :error="notifications.error.value"
          :empty="!shown.length"
          compact
          :title="filter === 'all' ? 'Bạn đã xem hết thông báo' : 'Không có thông báo trong mục này'"
          description="Giao việc, phê duyệt và lời nhắc sẽ hiện ở đây."
          @retry="notifications.refetch()"
        />
        <template v-for="group in groups" :key="group.label">
          <h3 class="notification-group">{{ group.label }}</h3>
          <div
            v-for="item in group.items"
            :key="item.id"
            class="notification-item"
            :class="{ unread: !item.read_at }"
          >
            <span class="notification-icon" :class="item.category">
              <component :is="ICONS[item.category ?? 'other']" :size="16" />
            </span>
            <button class="notification-open" type="button" @click="openItem(item)">
              <strong>{{ item.title }}</strong>
              <p v-if="item.body">{{ item.body }}</p>
              <small>{{ formatDate(item.created_at, true) }}</small>
            </button>
            <button
              v-if="!item.read_at"
              class="icon-button"
              type="button"
              aria-label="Đánh dấu đã đọc"
              title="Đánh dấu đã đọc"
              @click="markRead(item)"
            >
              <CheckCheck :size="16" />
            </button>
          </div>
        </template>
      </div>
    </section>
  </div>
</template>
