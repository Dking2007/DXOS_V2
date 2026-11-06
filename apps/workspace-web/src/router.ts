// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
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
      meta: { title: 'Kho tài liệu' },
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
      path: '/automations',
      component: () => import('./views/AutomationsView.vue'),
      meta: { title: 'Tự động hóa', capability: 'automations.manage' },
    },
    {
      path: '/automations/:id',
      component: () => import('./views/AutomationEditorView.vue'),
      meta: { title: 'Thiết kế luồng', capability: 'automations.manage', wide: true },
    },
    {
      path: '/assistant',
      component: () => import('./views/AssistantAdminView.vue'),
      meta: { title: 'Trợ lý AI', capability: 'assistant.manage' },
    },
    {
      path: '/packages',
      component: () => import('./views/PackagesView.vue'),
      meta: { title: 'Quy trình' },
    },
    {
      path: '/:pathMatch(.*)*',
      component: () => import('./views/NotFoundView.vue'),
      meta: { title: 'Không tìm thấy' },
    },
  ],
})
router.beforeEach(async (to) => {
  document.title = `${String(to.meta.title ?? 'Không gian làm việc')} · Desktiny`
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
