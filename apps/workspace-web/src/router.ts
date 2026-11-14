// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
import { brand, term } from './ui/appearance'
import { createRouter, createWebHistory } from 'vue-router'
import { useSession } from './stores/session'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/home' },
    {
      path: '/login',
      component: () => import('./views/LoginView.vue'),
      meta: { public: true, title: 'Đăng nhập' },
    },
    {
      path: '/home',
      component: () => import('./views/HomeView.vue'),
      meta: { title: 'Việc hôm nay' },
    },
    {
      path: '/drive',
      component: () => import('./views/DriveView.vue'),
      // Edge to edge under the top bar, like a file manager; the main navigation stays.
      meta: { title: 'Kho tài liệu', bleed: true },
    },
    {
      path: '/drive/:id/edit',
      component: () => import('./views/OfficeView.vue'),
      meta: { title: 'Chỉnh sửa tài liệu' },
    },
    {
      path: '/cases',
      component: () => import('./views/CasesView.vue'),
      meta: { title: 'Hồ sơ' },
    },
    {
      path: '/cases/:id',
      component: () => import('./views/CaseDetailView.vue'),
      meta: { title: 'Chi tiết hồ sơ' },
    },
    {
      path: '/approvals',
      component: () => import('./views/ApprovalsView.vue'),
      meta: { title: 'Cần phê duyệt' },
    },
    {
      path: '/profile',
      component: () => import('./views/ProfileView.vue'),
      meta: { title: 'Hồ sơ cá nhân' },
    },
    {
      path: '/settings',
      component: () => import('./views/SettingsView.vue'),
      meta: { title: 'Thiết lập' },
    },
    {
      path: '/tasks',
      component: () => import('./views/TasksView.vue'),
      meta: { title: 'Công việc' },
    },
    {
      path: '/tasks/:id',
      component: () => import('./views/TaskDetailView.vue'),
      meta: { title: 'Chi tiết công việc' },
    },
    {
      path: '/chat',
      component: () => import('./views/ChatView.vue'),
      // Full-bleed like a messaging app, but the main navigation stays as the user left it.
      meta: { title: 'Nhắn tin', bleed: true },
    },
    {
      path: '/feed',
      component: () => import('./views/FeedView.vue'),
      meta: { title: 'Bảng tin' },
    },
    {
      path: '/reports',
      component: () => import('./views/ReportsView.vue'),
      meta: { title: 'Báo cáo' },
    },
    {
      path: '/search',
      component: () => import('./views/SearchView.vue'),
      meta: { title: 'Tìm kiếm' },
    },
    {
      path: '/processes',
      component: () => import('./views/AutomationsView.vue'),
      meta: { title: 'Quy trình nghiệp vụ', capability: 'automations.manage' },
    },
    {
      path: '/processes/:id',
      component: () => import('./views/AutomationEditorView.vue'),
      meta: { title: 'Thiết kế quy trình', capability: 'automations.manage', wide: true },
    },
    // Links saved before Tự động hóa and Gói nghiệp vụ became one screen.
    { path: '/automations', redirect: (to) => ({ path: '/processes', query: { tab: 'automation', ...to.query } }) },
    { path: '/automations/:id', redirect: (to) => ({ path: `/processes/${String(to.params.id)}`, query: to.query }) },
    { path: '/packages', redirect: '/processes' },
    {
      path: '/assistant',
      component: () => import('./views/AssistantAdminView.vue'),
      meta: { title: 'Trợ lý AI', capability: 'assistant.manage' },
    },
    {
      path: '/plugins',
      component: () => import('./views/PluginsView.vue'),
      meta: { title: 'Plugin', capability: 'organization.manage' },
    },
    {
      path: '/apps/:pluginId/:index',
      component: () => import('./views/PluginPageView.vue'),
      meta: { title: 'Ứng dụng' },
    },
    {
      path: '/packs',
      component: () => import('./views/PacksView.vue'),
      meta: { title: 'Gói ngành', capability: 'organization.manage' },
    },
    {
      path: '/:pathMatch(.*)*',
      component: () => import('./views/NotFoundView.vue'),
      meta: { title: 'Không tìm thấy' },
    },
  ],
})
router.beforeEach(async (to) => {
  document.title = `${term(String(to.meta.title ?? 'Không gian làm việc'))} · ${brand.value.name}`
  const session = useSession()
  if (to.meta.public) return true
  if (!session.ready) {
    try {
      await session.load()
    } catch {
      return { path: '/login', query: { connection: 'failed' } }
    }
  }
  if (!session.user) return { path: '/login', query: { next: to.fullPath } }
  // Hiding a screen is convenience only; the API enforces the same permission.
  if (to.meta.capability && !session.can(String(to.meta.capability))) return { path: '/home' }
  return true
})
