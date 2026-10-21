<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter, RouterLink, RouterView } from 'vue-router'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import {
  BarChart3,
  Bell,
  CheckCheck,
  ChevronDown,
  ClipboardCheck,
  Files,
  FolderClosed,
  House,
  ListChecks,
  LogOut,
  Menu,
  MessagesSquare,
  Newspaper,
  PackageOpen,
  PanelLeftClose,
  PanelLeftOpen,
  Search,
  Settings2,
  ShieldCheck,
  Workflow,
  X,
} from 'lucide-vue-next'
import type { Notification } from '@dx/web-shared/types.ts'
import type { Page } from '@dx/web-shared/api.ts'
import { errorText, formatDate } from '@dx/web-shared/api.ts'
import { useSession } from './stores/session'
import { api } from './api'
import ModalDialog from '@dx/web-shared/components/ModalDialog.vue'
import StatePanel from '@dx/web-shared/components/StatePanel.vue'
const route = useRoute()
const router = useRouter()
const session = useSession()
const queryClient = useQueryClient()
const sidebar = ref(false)
const sidebarCollapsed = ref(window.localStorage.getItem('dx-workspace-sidebar-collapsed') === '1')
const notificationsOpen = ref(false)
const sessionError = ref('')
const allLinks = [
  { to: '/home', label: 'Không gian làm việc', icon: House },
  { to: '/tasks', label: 'Công việc', icon: ListChecks },
  { to: '/chat', label: 'Nhắn tin', icon: MessagesSquare, badge: 'chat' },
  { to: '/feed', label: 'Bảng tin', icon: Newspaper },
  { to: '/drive', label: 'Tài liệu', icon: FolderClosed },
  { to: '/cases', label: 'Hồ sơ', icon: Files },
  { to: '/approvals', label: 'Cần phê duyệt', icon: ClipboardCheck },
  { to: '/reports', label: 'Báo cáo', icon: BarChart3 },
  { to: '/automations', label: 'Tự động hóa', icon: Workflow, capability: 'automations.manage' },
  { to: '/packages', label: 'Gói nghiệp vụ', icon: PackageOpen },
  { to: '/settings', label: 'Thiết lập', icon: Settings2 },
]
const links = computed(() =>
  allLinks.filter((link) => !link.capability || session.can(link.capability)),
)
const chat = useQuery({
  queryKey: ['conversations'],
  queryFn: () =>
    api.request<Page<unknown> & { unread_total: number }>('/conversations'),
  enabled: computed(() => !!session.user),
  refetchInterval: 15_000,
})
const searchText = ref('')
function search() {
  const q = searchText.value.trim()
  if (q.length >= 2) router.push({ path: '/search', query: { q } })
}
async function openNotification(item: Notification) {
  const target = item.link || (item.case_id ? `/cases/${item.case_id}` : null)
  if (!item.read_at) await markRead(item)
  if (target) {
    notificationsOpen.value = false
    await router.push(target)
  }
}
const initials = computed(
  () =>
    session.user?.display_name
      .split(' ')
      .slice(-2)
      .map((word) => word[0])
      .join('')
      .toUpperCase() ?? '',
)
const notifications = useQuery({
  queryKey: ['notifications'],
  queryFn: () => api.request<Page<Notification>>('/notifications'),
  enabled: computed(() => !!session.user),
})
const unread = computed(() =>
  notifications.data.value?.items.some((item) => !item.read_at),
)
async function markRead(item: Notification) {
  await api.request(`/notifications/${item.id}`, {
    method: 'PATCH',
    body: JSON.stringify({}),
  })
  await queryClient.invalidateQueries({ queryKey: ['notifications'] })
}
async function logout() {
  try {
    await session.logout()
  } catch (error) {
    sessionError.value = errorText(error)
  }
}
function toggleSidebarCollapsed() {
  sidebarCollapsed.value = !sidebarCollapsed.value
  window.localStorage.setItem('dx-workspace-sidebar-collapsed', sidebarCollapsed.value ? '1' : '0')
}
</script>
<template>
  <RouterView v-if="route.meta.public" />
  <div
    v-else
    class="app-shell"
    :class="{ 'sidebar-collapsed': sidebarCollapsed || route.meta.wide }"
  >
    <a class="skip-link" href="#main-content">Đến nội dung chính</a>
    <div v-if="sidebar" class="sidebar-scrim" @click="sidebar = false" />
    <aside class="sidebar" :class="{ open: sidebar }">
      <RouterLink to="/home" class="brand" aria-label="Trang chủ"
        ><span class="brand-mark">dx<span /></span
        ><span>Workspace<small>KHÔNG GIAN LÀM VIỆC SỐ</small></span></RouterLink
      >
      <button
        class="icon-button sidebar-close"
        aria-label="Đóng điều hướng"
        @click="sidebar = false"
      >
        <X :size="20" />
      </button>
      <div class="workspace-label">
        <span class="organization-icon"><ShieldCheck :size="17" /></span>
        <div><strong>e-Office</strong><small>Không gian nội bộ</small></div>
        <ChevronDown :size="14" />
      </div>
      <span class="nav-label">LÀM VIỆC</span>
      <nav aria-label="Điều hướng chính">
        <RouterLink
          v-for="link in links"
          :key="link.to"
          :to="link.to"
          class="nav-link"
          :title="link.label"
          :aria-label="link.label"
          @click="sidebar = false"
          ><component :is="link.icon" :size="19" :stroke-width="1.7" /><span>{{
            link.label
          }}</span
          ><i
            v-if="link.badge === 'chat' && chat.data.value?.unread_total"
            class="nav-badge"
            :aria-label="`${chat.data.value.unread_total} tin chưa đọc`"
            >{{ chat.data.value.unread_total }}</i
          ></RouterLink
        >
      </nav>
      <div class="sidebar-bottom">
        <button class="sidebar-collapse" type="button" :aria-label="sidebarCollapsed ? 'Mở rộng thanh bên' : 'Thu gọn thanh bên'" :title="sidebarCollapsed ? 'Mở rộng thanh bên' : 'Thu gọn thanh bên'" :aria-expanded="!sidebarCollapsed" @click="toggleSidebarCollapsed">
          <PanelLeftOpen v-if="sidebarCollapsed" :size="18" />
          <PanelLeftClose v-else :size="18" />
          <span>{{ sidebarCollapsed ? 'Mở rộng menu' : 'Thu gọn menu' }}</span>
        </button>
        <div class="privacy-note">
          <ShieldCheck :size="17" /><span
            >Đúng người. Đúng quyền.<br />Giữ trọn lịch sử.</span
          >
        </div>
        <a
          v-if="session.user?.roles?.includes('technical_admin')"
          href="/console/"
          class="console-link"
          aria-label="Mở Core console"
          title="Mở Core console"
          ><span class="console-link-text">Mở Core console</span><span>↗</span></a
        >
        <div class="sidebar-version">
          <span class="connection-dot" /> Bản pilot · e-Office
        </div>
      </div>
    </aside>
    <div class="workspace-main">
      <header class="topbar">
        <div class="topbar-location">
          <button
            class="icon-button mobile-toggle"
            aria-label="Mở điều hướng"
            @click="sidebar = true"
          >
            <Menu :size="21" /></button
          ><span>Không gian nội bộ</span><span class="topbar-divider">/</span
          ><strong>{{ route.meta.title }}</strong>
        </div>
        <form class="topbar-search" role="search" @submit.prevent="search">
          <Search :size="16" /><input
            v-model="searchText"
            type="search"
            placeholder="Tìm việc, hồ sơ, tài liệu…"
            aria-label="Tìm kiếm toàn bộ"
          />
        </form>
        <div class="topbar-actions">
          <button
            class="icon-button notification-button"
            aria-label="Mở thông báo"
            @click="notificationsOpen = true"
          >
            <Bell :size="20" /><i v-if="unread" /></button
          ><span class="topbar-separator" />
          <div class="user-profile">
            <span class="avatar">{{ initials }}</span>
            <div>
              <strong>{{ session.user?.display_name }}</strong
              ><small>{{
                session.user?.role === 'director'
                  ? 'Ban giám đốc'
                  : session.user?.role === 'manager'
                    ? 'Lãnh đạo phòng'
                    : session.user?.role === 'technical_admin'
                      ? 'Quản trị kỹ thuật'
                      : 'Cán bộ / nhân viên'
              }}</small>
            </div>
          </div>
          <button class="icon-button" aria-label="Đăng xuất" @click="logout">
            <LogOut :size="18" />
          </button>
        </div>
      </header>
      <main id="main-content" class="page-content" :class="{ wide: route.meta.wide }">
        <div v-if="sessionError" class="notice error error-inline" role="alert">
          {{ sessionError }}
        </div>
        <RouterView :key="String(route.params.id ?? route.path)" />
      </main>
      <footer v-if="!route.meta.wide" class="app-footer">
        <span>DX Workspace</span
        ><span>Dữ liệu nghiệp vụ được kiểm soát theo quyền truy cập.</span>
      </footer>
    </div>
    <ModalDialog
      v-if="notificationsOpen"
      title="Thông báo của bạn"
      @close="notificationsOpen = false"
      ><StatePanel
        :loading="notifications.isPending.value"
        :error="notifications.error.value"
        :empty="notifications.data.value?.items.length === 0"
        title="Bạn đã cập nhật mọi việc"
        description="Thông báo giao việc và phê duyệt sẽ xuất hiện tại đây."
        @retry="notifications.refetch()" />
      <div
        v-for="item in notifications.data.value?.items"
        :key="item.id"
        class="notification-item"
        :class="{ unread: !item.read_at }"
      >
        <button class="notification-open" @click="openNotification(item)">
          <strong>{{ item.title }}</strong>
          <p v-if="item.body">{{ item.body }}</p>
          <small>{{ formatDate(item.created_at, true) }}</small>
        </button>
        <button
          v-if="!item.read_at"
          class="icon-button"
          aria-label="Đánh dấu đã đọc"
          @click="markRead(item)"
        >
          <CheckCheck :size="18" />
        </button></div
    ></ModalDialog>
  </div>
</template>
