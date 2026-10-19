<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, RouterLink, RouterView } from 'vue-router'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import {
  Bell,
  CheckCheck,
  ChevronDown,
  ClipboardCheck,
  Files,
  FolderClosed,
  House,
  LogOut,
  Menu,
  Settings2,
  ShieldCheck,
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
const session = useSession()
const queryClient = useQueryClient()
const sidebar = ref(false)
const notificationsOpen = ref(false)
const sessionError = ref('')
const links = [
  { to: '/home', label: 'Không gian làm việc', icon: House },
  { to: '/drive', label: 'Tài liệu', icon: FolderClosed },
  { to: '/cases', label: 'Hồ sơ', icon: Files },
  { to: '/approvals', label: 'Cần phê duyệt', icon: ClipboardCheck },
  { to: '/settings', label: 'Thiết lập', icon: Settings2 },
]
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
</script>
<template>
  <RouterView v-if="route.meta.public" />
  <div v-else class="app-shell">
    <a class="skip-link" href="#main-content">Đến nội dung chính</a>
    <div v-if="sidebar" class="sidebar-scrim" @click="sidebar = false" />
    <aside class="sidebar" :class="{ open: sidebar }">
      <RouterLink to="/home" class="brand"
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
          @click="sidebar = false"
          ><component :is="link.icon" :size="19" :stroke-width="1.7" /><span>{{
            link.label
          }}</span></RouterLink
        >
      </nav>
      <div class="sidebar-bottom">
        <div class="privacy-note">
          <ShieldCheck :size="17" /><span
            >Đúng người. Đúng quyền.<br />Giữ trọn lịch sử.</span
          >
        </div>
        <a
          v-if="session.user?.roles?.includes('technical_admin')"
          href="/console/"
          class="console-link"
          >Mở Core console <span>↗</span></a
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
      <main id="main-content" class="page-content">
        <div v-if="sessionError" class="notice error error-inline" role="alert">
          {{ sessionError }}
        </div>
        <RouterView :key="String(route.params.id ?? route.path)" />
      </main>
      <footer class="app-footer">
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
        <div>
          <strong>{{ item.title }}</strong>
          <p v-if="item.body">{{ item.body }}</p>
          <small>{{ formatDate(item.created_at, true) }}</small>
        </div>
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
