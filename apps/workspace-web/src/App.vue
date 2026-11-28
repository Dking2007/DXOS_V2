<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, RouterLink, RouterView } from 'vue-router'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { api } from './api'
import type { PluginSlotItem } from './components/plugins/PluginFrames.vue'
import {
  AppWindow,
  LoaderCircle,
  LogOut,
  Menu,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  Search,
  SlidersHorizontal,
  Sun,
  X,
} from 'lucide-vue-next'
import { errorText } from '@dx/web-shared/api.ts'
import { useSession } from './stores/session'
import { badgeText, navTone, visibleGroups } from './ui/nav'
import type { NavGroup } from './ui/nav'
import { useOverview } from './ui/overview'
import { paletteRequest } from './ui/palette'
import { brand, term } from './ui/appearance'
import { cycleTheme, isDark } from './ui/theme'
import { roleLabel } from './ui/labels'
import { isCollapsed, sidebarPrefs, toggleLabel, toggleSidebar } from './ui/sidebar'
import { confirmLeaveAll, LOGOUT_QUESTION, resetLeaveConsent } from './ui/unsaved'
import AvatarPhoto from './components/AvatarPhoto.vue'
import ConfirmHost from '@dx/web-shared/components/ConfirmHost.vue'
import AppToaster from './components/shell/AppToaster.vue'
import BackToTop from './components/shell/BackToTop.vue'
import CommandPalette from './components/shell/CommandPalette.vue'
import CreateMenu from './components/shell/CreateMenu.vue'
import MobileNav from './components/shell/MobileNav.vue'
import NotificationPanel from './components/shell/NotificationPanel.vue'
import OnboardingTour from './components/shell/OnboardingTour.vue'
import PageHelp from './components/shell/PageHelp.vue'
import AssistantWidget from './assistant/AssistantWidget.vue'
import AiBusy from './ai/AiBusy.vue'
const route = useRoute()
const session = useSession()
const sidebar = ref(false)
// Canvas pages start folded; the person's own choice (kept per kind of page) always wins.
const sidebarCollapsed = computed(() => isCollapsed(sidebarPrefs.value, !!route.meta.wide))
const sidebarLabel = computed(() => toggleLabel(sidebarCollapsed.value))
const sessionError = ref('')
const loggingOut = ref(false)
const palette = ref<InstanceType<typeof CommandPalette>>()
watch(paletteRequest, (request) => request && palette.value?.show(request.text))
// Pages of connected plugins get their own group in the sidebar.
const pluginPages = useQuery({
  queryKey: ['plugin-slots', 'page'],
  queryFn: () => api.request<{ items: PluginSlotItem[] }>('/plugin-slots?slot=page').then((result) => result.items),
  enabled: computed(() => !!session.user),
  staleTime: 60_000,
})
const groups = computed(() => {
  const base = visibleGroups(session.can)
  const pages = pluginPages.data.value ?? []
  if (!pages.length) return base
  const apps: NavGroup = {
    label: 'Ứng dụng',
    links: pages.map((page) => ({
      key: `app:${page.plugin_id}:${page.index}`,
      to: `/apps/${page.plugin_id}/${page.index}`,
      label: page.title,
      icon: AppWindow,
      hint: page.plugin_name,
    })),
  }
  return [...base.slice(0, 1), apps, ...base.slice(1)]
})
const overview = useOverview()
const counts = computed(() => overview.data.value?.counts)
const queryClient = useQueryClient()
// Most actions end with a navigation; refreshing here keeps the badges honest.
watch(
  () => route.path,
  () => void queryClient.invalidateQueries({ queryKey: ['me-overview'] }),
)
watch(
  () => route.fullPath,
  () => {
    // The phone drawer never outlives the page it was opened on.
    sidebar.value = false
  },
)
function onKey(event: KeyboardEvent) {
  if (event.key === 'Escape' && sidebar.value) {
    sidebar.value = false
    document.querySelector<HTMLElement>('.mobile-toggle')?.focus()
  }
}
onMounted(() => document.addEventListener('keydown', onKey))
onBeforeUnmount(() => document.removeEventListener('keydown', onKey))
// Re-read on every theme change so the toggle icon follows the choice.
const dark = computed(() => isDark())
const initials = computed(
  () =>
    session.user?.display_name
      .split(' ')
      .slice(-2)
      .map((word) => word[0])
      .join('')
      .toUpperCase() ?? '',
)
async function logout() {
  if (loggingOut.value || !(await confirmLeaveAll(LOGOUT_QUESTION))) return
  loggingOut.value = true
  sessionError.value = ''
  try {
    await session.logout()
  } catch (error) {
    sessionError.value = errorText(error)
    resetLeaveConsent()
    loggingOut.value = false
  }
}
function toggleSidebarCollapsed() {
  toggleSidebar(!!route.meta.wide)
}
</script>
<template>
  <RouterView v-if="route.meta.public" />
  <div
    v-else
    class="app-shell"
    :class="{ 'sidebar-collapsed': sidebarCollapsed }"
  >
    <a class="skip-link" href="#main-content">Đến nội dung chính</a>
    <div v-if="sidebar" class="sidebar-scrim" @click="sidebar = false" />
    <aside class="sidebar" :class="{ open: sidebar }">
      <div class="sidebar-head">
        <RouterLink to="/home" class="brand" aria-label="Trang chủ"
          ><span class="brand-mark" :class="{ 'has-logo': !!brand.logo }" aria-hidden="true"
            ><img v-if="brand.logo" :src="brand.logo" alt="" width="28" height="28" /><template v-else>{{
              brand.name.charAt(0)
            }}</template></span
          ><span class="brand-text" :title="[brand.name, brand.org].filter(Boolean).join(' · ')"
            ><span>{{ brand.name }}</span><small v-if="brand.org">{{ brand.org }}</small></span
          ></RouterLink
        >
        <button
          class="sidebar-collapse"
          type="button"
          :aria-label="sidebarLabel"
          :title="sidebarLabel"
          :aria-expanded="!sidebarCollapsed"
          aria-controls="main-navigation"
          @click="toggleSidebarCollapsed"
        >
          <PanelLeftOpen v-if="sidebarCollapsed" :size="18" aria-hidden="true" />
          <PanelLeftClose v-else :size="18" aria-hidden="true" />
        </button>
      </div>
      <button
        class="icon-button sidebar-close"
        type="button"
        aria-label="Đóng điều hướng"
        title="Đóng điều hướng"
        @click="sidebar = false"
      >
        <X :size="20" aria-hidden="true" />
      </button>
      <nav id="main-navigation" aria-label="Điều hướng chính" data-tour="nav" class="nav-groups">
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
            ><span class="nav-tile" :data-tone="link.tone ?? navTone(link.key)" aria-hidden="true"
              ><component :is="link.icon" :size="16" :stroke-width="1.9" /></span
            ><span>{{
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
        <a
          v-if="session.user?.roles?.includes('technical_admin')"
          href="/console/"
          class="console-link"
          aria-label="Mở bảng điều khiển kỹ thuật của nền tảng"
          title="Công cụ cho quản trị kỹ thuật: schema, luồng, lượt chạy, nhật ký nền tảng. Không dùng cho nghiệp vụ hằng ngày."
          ><span class="console-link-text">Bảng điều khiển kỹ thuật</span><span aria-hidden="true">↗</span></a
        >
      </div>
    </aside>
    <div class="workspace-main">
      <header class="topbar">
        <div class="topbar-location">
          <button
            class="icon-button mobile-toggle"
            type="button"
            aria-label="Mở điều hướng"
            title="Mở điều hướng"
            :aria-expanded="sidebar"
            @click="sidebar = true"
          >
            <Menu :size="21" aria-hidden="true" /></button
          ><span class="topbar-crumb" title="Không gian nội bộ">Không gian nội bộ</span><span class="topbar-divider" aria-hidden="true">/</span
          ><strong :title="term(String(route.meta.title ?? ''))">{{ term(String(route.meta.title ?? '')) }}</strong><PageHelp />
        </div>
        <button
          class="topbar-search"
          type="button"
          data-tour="search"
          aria-label="Tìm kiếm hoặc gõ lệnh (Ctrl + K)"
          aria-keyshortcuts="Control+K"
          @click="palette?.show()"
        >
          <Search :size="16" aria-hidden="true" /><span>Tìm việc, hồ sơ, tài liệu…</span><kbd aria-hidden="true">Ctrl K</kbd>
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
            <Sun v-if="dark" :size="19" aria-hidden="true" /><Moon v-else :size="19" aria-hidden="true" />
          </button>
          <RouterLink to="/preferences" class="icon-button preferences-link" title="Cài đặt cá nhân" aria-label="Cài đặt cá nhân"
            ><SlidersHorizontal :size="19" aria-hidden="true"
          /></RouterLink>
          <NotificationPanel data-tour="notifications" />
          <span class="topbar-separator" />
          <RouterLink to="/profile" class="user-profile" title="Hồ sơ cá nhân" aria-label="Hồ sơ cá nhân">
            <span class="avatar" aria-hidden="true">{{ initials }}<AvatarPhoto :url="session.user?.avatar_url" /></span>
            <div>
              <strong>{{ session.user?.display_name }}</strong
              ><small>{{ session.user?.job_title || roleLabel(session.user?.role) }}</small>
            </div>
          </RouterLink>
          <button
            class="icon-button"
            type="button"
            :aria-label="loggingOut ? 'Đang đăng xuất…' : 'Đăng xuất'"
            :title="loggingOut ? 'Đang đăng xuất…' : 'Đăng xuất'"
            :disabled="loggingOut"
            :aria-busy="loggingOut"
            @click="logout"
          >
            <LoaderCircle v-if="loggingOut" :size="18" class="spin" aria-hidden="true" />
            <LogOut v-else :size="18" aria-hidden="true" />
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
        <span>{{ brand.org || brand.name }}</span
        ><span>Dữ liệu nghiệp vụ được kiểm soát theo quyền truy cập.</span>
      </footer>
    </div>
    <MobileNav v-if="!route.meta.wide" :counts="counts" @more="sidebar = true" />
    <BackToTop />
    <CommandPalette ref="palette" />
    <OnboardingTour />
    <AssistantWidget />
    <AiBusy />
  </div>
  <AppToaster />
  <ConfirmHost />
</template>
