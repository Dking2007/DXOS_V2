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
      meta: { title: 'Tổng quan' },
    },
    {
      path: '/drive',
      component: () => import('./views/DriveView.vue'),
      meta: { title: 'Tài liệu' },
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
      path: '/:pathMatch(.*)*',
      component: () => import('./views/NotFoundView.vue'),
      meta: { title: 'Không tìm thấy' },
    },
  ],
})
router.beforeEach(async (to) => {
  document.title = `${String(to.meta.title ?? 'Không gian làm việc')} · DX Workspace`
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
  return true
})
