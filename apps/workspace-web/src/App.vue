<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, RouterLink, RouterView } from 'vue-router'
import { useQueryClient } from '@tanstack/vue-query'
import {
  LogOut,
  Menu,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  Search,
  ShieldCheck,
  Sun,
  X,
} from 'lucide-vue-next'
import { errorText } from '@dx/web-shared/api.ts'
import { useSession } from './stores/session'
import { badgeText, visibleGroups } from './ui/nav'
import { useOverview } from './ui/overview'
import { cycleTheme, isDark, theme } from './ui/theme'
import { roleLabel } from './ui/labels'
import AppToaster from './components/shell/AppToaster.vue'
import CommandPalette from './components/shell/CommandPalette.vue'
import CreateMenu from './components/shell/CreateMenu.vue'
import MobileNav from './components/shell/MobileNav.vue'
import NotificationPanel from './components/shell/NotificationPanel.vue'
import OnboardingTour from './components/shell/OnboardingTour.vue'
import AssistantWidget from './assistant/AssistantWidget.vue'
const route = useRoute()
const session = useSession()
const sidebar = ref(false)
const sidebarCollapsed = ref(readCollapsed())
const sessionError = ref('')
const palette = ref<InstanceType<typeof CommandPalette>>()
const groups = computed(() => visibleGroups(session.can))
const overview = useOverview()
const counts = computed(() => overview.data.value?.counts)
const queryClient = useQueryClient()
// Most actions end with a navigation; refreshing here keeps the badges honest.
watch(
  () => route.fullPath,
  () => queryClient.invalidateQueries({ queryKey: ['me-overview'] }),
)
// Re-read on every theme change so the toggle icon follows the choice.
const dark = computed(() => theme.value === 'dark' || (theme.value === 'system' && isDark()))
const initials = computed(
  () =>
    session.user?.display_name
      .split(' ')
      .slice(-2)
      .map((word) => word[0])
      .join('')
      .toUpperCase() ?? '',
)
function readCollapsed() {
  try {
    return window.localStorage.getItem('dx-workspace-sidebar-collapsed') === '1'
  } catch {
    return false
  }
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
  try {
    window.localStorage.setItem('dx-workspace-sidebar-collapsed', sidebarCollapsed.value ? '1' : '0')
  } catch {
    // The choice still holds for this visit.
  }
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
        ><span class="brand-mark">D<span /></span
        ><span>Desktiny<small>VĂN PHÒNG SỐ</small></span></RouterLink
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
      </div>
      <nav aria-label="Điều hướng chính" data-tour="nav" class="nav-groups">
        <div
          v-for="group in groups"
          :key="group.label"
          class="nav-group"
          :data-tour="group.label === 'Quản trị' ? 'nav-admin' : undefined"
        >
          <span class="nav-label">{{ group.label }}</span>
          <RouterLink
            v-for="link in group.links"
            :key="link.to"
            :to="link.to"
            class="nav-link"
            :title="link.label"
            @click="sidebar = false"
            ><component :is="link.icon" :size="19" :stroke-width="1.7" aria-hidden="true" /><span>{{
              link.label
            }}</span
            ><i
              v-if="counts && link.badge && link.badge(counts)"
              class="nav-badge"
              :aria-label="`${link.badge(counts)} mục đang chờ`"
              >{{ badgeText(link.badge(counts)) }}</i
            ></RouterLink
          >
        </div>
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
          aria-label="Mở bảng điều khiển kỹ thuật của nền tảng"
          title="Công cụ cho quản trị kỹ thuật: schema, luồng, lượt chạy, nhật ký nền tảng. Không dùng cho nghiệp vụ hằng ngày."
          ><span class="console-link-text">Bảng điều khiển kỹ thuật</span><span aria-hidden="true">↗</span></a
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
          ><span class="topbar-crumb">Không gian nội bộ</span><span class="topbar-divider" aria-hidden="true">/</span
          ><strong>{{ route.meta.title }}</strong>
        </div>
        <button
          class="topbar-search"
          type="button"
          data-tour="search"
          aria-label="Tìm kiếm hoặc gõ lệnh (Ctrl + K)"
          @click="palette?.show()"
        >
          <Search :size="16" /><span>Tìm việc, hồ sơ, tài liệu…</span><kbd>Ctrl K</kbd>
        </button>
        <div class="topbar-actions">
          <CreateMenu data-tour="create" />
          <button
            class="icon-button theme-toggle"
            type="button"
            :aria-label="dark ? 'Chuyển sang giao diện sáng' : 'Chuyển sang giao diện tối'"
            :title="dark ? 'Giao diện sáng' : 'Giao diện tối'"
            @click="cycleTheme"
          >
            <Sun v-if="dark" :size="19" /><Moon v-else :size="19" />
          </button>
          <NotificationPanel data-tour="notifications" />
          <span class="topbar-separator" />
          <div class="user-profile">
            <span class="avatar" aria-hidden="true">{{ initials }}</span>
            <div>
              <strong>{{ session.user?.display_name }}</strong
              ><small>{{ roleLabel(session.user?.role) }}</small>
            </div>
          </div>
          <button class="icon-button" aria-label="Đăng xuất" title="Đăng xuất" @click="logout">
            <LogOut :size="18" />
          </button>
        </div>
      </header>
      <main id="main-content" class="page-content" :class="{ wide: route.meta.wide || route.meta.bleed }" tabindex="-1">
        <div v-if="sessionError" class="notice error error-inline" role="alert">
          {{ sessionError }}
        </div>
        <RouterView :key="String(route.params.id ?? route.path)" />
      </main>
      <footer v-if="!route.meta.wide && !route.meta.bleed" class="app-footer">
        <span>Desktiny</span
        ><span>Dữ liệu nghiệp vụ được kiểm soát theo quyền truy cập.</span>
      </footer>
    </div>
    <MobileNav v-if="!route.meta.wide" :counts="counts" @more="sidebar = true" />
    <CommandPalette ref="palette" />
    <OnboardingTour />
    <AssistantWidget />
  </div>
  <AppToaster />
</template>
