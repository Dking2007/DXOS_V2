<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import {
  ArrowRightLeft,
  Building2,
  Check,
  Crown,
  Filter,
  History,
  ListTree,
  Network,
  Pencil,
  Plus,
  Save,
  Search,
  ShieldCheck,
  Table2,
  TriangleAlert,
  UserPlus,
  X,
} from 'lucide-vue-next'
import { api } from '../api'
import { useSession } from '../stores/session'
import { ApiError, errorText } from '@dx/web-shared/api.ts'
import type { Page } from '@dx/web-shared/api.ts'
import type { Department, User } from '@dx/web-shared/types.ts'
import StatePanel from '@dx/web-shared/components/StatePanel.vue'
import ModalDialog from '@dx/web-shared/components/ModalDialog.vue'
import RoleMatrix from '../components/RoleMatrix.vue'
import AuditLog from '../components/AuditLog.vue'
import AvatarPhoto from '../components/AvatarPhoto.vue'
import OrgChart from '../components/org/OrgChart.vue'
import OrgDrawer from '../components/org/OrgDrawer.vue'
import OrgStats from '../components/org/OrgStats.vue'
import OrgTreeView from '../components/org/OrgTreeView.vue'
import HighlightText from '../components/org/HighlightText.vue'
import {
  allowedParents,
  buildOrgTree,
  flatten,
  needingAttention,
  orgStats,
  searchOrg,
  UNASSIGNED_ID,
  WARNING_LABELS,
  type OrgNode,
} from '../components/org/orgTree'
import '../components/org/org.css'
import { initialsOf } from '../ui/people'
import { fold } from '@dx/web-shared/text.ts'
import { permissionLabel, PERMISSIONS, ROLE_LABELS, roleLabel } from '../ui/labels'
import { brand } from '../ui/appearance'
import { toast } from '../ui/toast'
import { confirmDiscard, useUnsavedGuard } from '../ui/unsaved'

const session = useSession()
const queryClient = useQueryClient()
const route = useRoute()
const router = useRouter()

// ---- Tabs (kept in the address so a reload or a shared link opens the same one) ----
// The look moved to Cài đặt cá nhân (/preferences); the router sends ?tab=appearance there.
type SettingsTab = 'organization' | 'permissions' | 'audit'
const requestedTab = String(route.query.tab ?? '')
// Forms and their approval steps are designed on the process screen now.
if (requestedTab === 'forms') void router.replace('/processes')
const tab = ref<SettingsTab>(
  (['organization', 'permissions', 'audit'] as const).find(
    (key) => key === requestedTab && (key !== 'audit' || session.can('audit.read')),
  ) ?? (['director', 'manager'].includes(session.user?.role ?? '') ? 'organization' : 'permissions'),
)
const TABS = computed(() =>
  [
    { key: 'organization' as const, label: 'Cơ cấu tổ chức', icon: Network },
    { key: 'permissions' as const, label: 'Vai trò & quyền', icon: ShieldCheck },
    { key: 'audit' as const, label: 'Nhật ký hoạt động', icon: History, hidden: !session.can('audit.read') },
  ].filter((item) => !item.hidden),
)
// The permission matrix keeps its edits in memory; leaving its tab would lose them silently.
const matrixDirty = ref(false)
async function selectTab(next: SettingsTab) {
  if (next === tab.value) return
  if (tab.value === 'permissions' && !(await confirmDiscard(matrixDirty.value))) return
  matrixDirty.value = false
  tab.value = next
}
watch(tab, (value) => {
  if (route.query.tab !== value) void router.replace({ query: { ...route.query, tab: value } })
})

// ---- Data ----
const users = useQuery({
  queryKey: ['users'],
  queryFn: () => api.request<Page<User>>('/users'),
})
const departments = useQuery({
  queryKey: ['departments'],
  queryFn: () => api.request<Page<Department>>('/departments'),
})
// The server checks the same capability; the role matrix can grant it to any role.
const canManageOrg = computed(() => session.can('organization.manage'))
const orgLoading = computed(() => departments.isPending.value || users.isPending.value)
const orgError = computed(() => departments.error.value ?? users.error.value)
function retryOrg() {
  void departments.refetch()
  void users.refetch()
}

// ---- Organisation views ----
type OrgView = 'chart' | 'tree' | 'table'
const VIEW_KEY = 'dx-org-view'
const VIEWS: { key: OrgView; label: string; icon: typeof Network }[] = [
  { key: 'chart', label: 'Sơ đồ', icon: Network },
  { key: 'tree', label: 'Cây', icon: ListTree },
  { key: 'table', label: 'Bảng', icon: Table2 },
]
function storedView(): OrgView {
  try {
    const value = window.localStorage.getItem(VIEW_KEY)
    if (value === 'chart' || value === 'tree' || value === 'table') return value
  } catch {
    // Storage may be blocked; fall back to the default below.
  }
  // A chart is hard to read on a phone; the outline fits its width.
  return window.matchMedia?.('(max-width: 640px)').matches ? 'tree' : 'chart'
}
const orgView = ref<OrgView>(storedView())
watch(orgView, (value) => {
  try {
    window.localStorage.setItem(VIEW_KEY, value)
  } catch {
    // Not remembered in private windows; the view still changes for this visit.
  }
})

const tree = computed(() => buildOrgTree(departments.data.value?.items ?? [], users.data.value?.items ?? []))
const stats = computed(() => orgStats(tree.value))
const orgQuery = ref('')
const search = computed(() => searchOrg(tree.value, orgQuery.value))
const roleFilter = ref('')
const attentionOn = ref(false)
const attention = computed(() => (attentionOn.value ? needingAttention(tree.value) : null))
const rootTitle = computed(() => brand.value.org || 'Toàn tổ chức')
const roleOptions = computed(() => {
  const keys = new Set(Object.keys(ROLE_LABELS))
  for (const user of users.data.value?.items ?? []) keys.add(user.role || 'staff')
  return [...keys].map((key) => ({ key, label: ROLE_LABELS[key] ?? key }))
})
const filtersOn = computed(() => !!orgQuery.value.trim() || !!roleFilter.value || attentionOn.value)
function clearFilters() {
  orgQuery.value = ''
  roleFilter.value = ''
  attentionOn.value = false
}
const searchSummary = computed(() => {
  if (!orgQuery.value.trim()) return ''
  const units = search.value.departments.size
  const people = search.value.members.size
  if (!units && !people) return 'Không có kết quả'
  return [units && `${units} phòng ban`, people && `${people} người`].filter(Boolean).join(', ')
})

const drawerTarget = ref<string | null>(null)
function openUnit(id: string) {
  drawerTarget.value = id
}

// Table view: departments in tree order, people filtered by the shared search and role.
const memberDepartment = ref('')
const departmentRows = computed(() => {
  const query = orgQuery.value.trim()
  return flatten(tree.value).filter((node) => {
    if (attention.value && !attention.value.has(node.id)) return false
    if (query && !search.value.departments.has(node.id)) return false
    return true
  })
})
const members = computed(() => {
  const needle = fold(orgQuery.value.trim())
  return (users.data.value?.items ?? []).filter((user) => {
    if (memberDepartment.value === 'none' && user.department_id) return false
    if (memberDepartment.value && memberDepartment.value !== 'none' && user.department_id !== memberDepartment.value)
      return false
    if (roleFilter.value && (user.role || 'staff') !== roleFilter.value) return false
    return !needle || fold([user.display_name, user.job_title, user.contact_email].filter(Boolean).join(' ')).includes(needle)
  })
})
// Picker labels show the hierarchy with an em space per level.
const indented = (node: OrgNode) => `${' '.repeat(node.depth - 1)}${node.department.name}`
const departmentName = (id?: string | null) => (id ? (tree.value.byId.get(id)?.department.name ?? '') : '')

// ---- Dialogs: department, new member, move a member ----
const modal = ref<'department' | 'user' | 'assign' | null>(null)
const error = ref<unknown>(null)
const busy = ref(false)
const depName = ref('')
const depCode = ref('')
const depParent = ref('')
const depManager = ref('')
const editDepartment = ref<Department | null>(null)
const userSubject = ref('')
const userName = ref('')
const userRole = ref('staff')
const userDepartment = ref('')
const assignUser = ref('')
const assignDepartment = ref('')
const opened = ref('')
function modalState() {
  if (modal.value === 'department') return JSON.stringify([depName.value, depCode.value, depParent.value, depManager.value])
  if (modal.value === 'user') return JSON.stringify([userSubject.value, userName.value, userRole.value, userDepartment.value])
  if (modal.value === 'assign') return JSON.stringify([assignUser.value, assignDepartment.value])
  return ''
}
const dialogDirty = computed(() => !!modal.value && modalState() !== opened.value)
useUnsavedGuard(dialogDirty)
async function closeModal() {
  if (busy.value) return
  if (await confirmDiscard(dialogDirty.value)) modal.value = null
}
function show(type: NonNullable<typeof modal.value>) {
  modal.value = type
  error.value = null
  opened.value = modalState()
}
function openDepartment(parentId: string | null = null) {
  editDepartment.value = null
  depName.value = ''
  depCode.value = ''
  depParent.value = parentId ?? ''
  depManager.value = ''
  show('department')
}
function editDep(item: Department) {
  editDepartment.value = item
  depName.value = item.name
  depCode.value = item.code ?? ''
  depParent.value = item.parent_id ?? ''
  depManager.value = item.manager_id ?? ''
  show('department')
}
function editById(id: string) {
  const node = tree.value.byId.get(id)
  if (node) editDep(node.department)
}
function openUser(departmentId: string | null = null) {
  userSubject.value = ''
  userName.value = ''
  userRole.value = 'staff'
  userDepartment.value = departmentId ?? ''
  show('user')
}
function openAssign(userId: string | null, departmentId: string | null) {
  assignUser.value = userId ?? ''
  assignDepartment.value = departmentId ?? ''
  show('assign')
}

// Parent choices in tree order; a department cannot sit under itself or under one of its own.
const parentChoices = computed(() => {
  const allowed = allowedParents(tree.value, editDepartment.value?.id ?? null)
  return flatten(tree.value).map((node) => ({
    id: node.id,
    label: indented(node),
    disabled: !allowed.has(node.id),
    reason:
      node.id === editDepartment.value?.id ? ' (chính phòng này)' : !allowed.has(node.id) ? ' (phòng con của phòng này)' : '',
  }))
})
const managerGroups = computed(() => {
  const all = [...(users.data.value?.items ?? [])].sort((a, b) => a.display_name.localeCompare(b.display_name, 'vi'))
  const home = editDepartment.value?.id
  if (!home) return [{ label: '', people: all }]
  return [
    { label: 'Thành viên của phòng', people: all.filter((user) => user.department_id === home) },
    { label: 'Người ở phòng khác', people: all.filter((user) => user.department_id !== home) },
  ].filter((group) => group.people.length)
})
const codeTaken = computed(() => {
  const code = fold(depCode.value.trim())
  return (
    !editDepartment.value &&
    !!code &&
    (departments.data.value?.items ?? []).some((item) => fold(item.code ?? '') === code)
  )
})
const subjectTaken = computed(() => {
  const subject = userSubject.value.trim()
  return !!subject && (users.data.value?.items ?? []).some((user) => user.subject === subject)
})
const assignCurrent = computed(() => (users.data.value?.items ?? []).find((user) => user.id === assignUser.value))
// Why "Lưu" cannot be pressed yet; empty when it can.
const blocker = computed(() => {
  if (modal.value === 'department') {
    if (!depName.value.trim()) return 'Nhập tên phòng ban'
    if (!editDepartment.value && !depCode.value.trim()) return 'Nhập mã phòng ban'
    if (codeTaken.value) return 'Mã phòng ban đã được dùng'
    if (depParent.value && parentChoices.value.find((item) => item.id === depParent.value)?.disabled)
      return 'Phòng cha không hợp lệ'
    if (editDepartment.value && !dialogDirty.value) return 'Chưa có thay đổi nào'
  }
  if (modal.value === 'user') {
    if (!userSubject.value.trim()) return 'Nhập mã tài khoản đăng nhập'
    if (subjectTaken.value) return 'Mã tài khoản đã gắn với một thành viên'
    if (!userName.value.trim()) return 'Nhập tên hiển thị'
  }
  if (modal.value === 'assign') {
    if (!assignUser.value) return 'Chọn thành viên'
    if ((assignCurrent.value?.department_id ?? '') === assignDepartment.value) return 'Người này đang ở phòng đã chọn'
  }
  return ''
})
const modalTitle = computed(() => {
  if (modal.value === 'department') return editDepartment.value ? 'Cập nhật phòng ban' : 'Thêm phòng ban'
  if (modal.value === 'assign') return 'Xếp thành viên vào phòng ban'
  return 'Thêm thành viên'
})

async function save() {
  if (busy.value || blocker.value) return
  busy.value = true
  error.value = null
  const kind = modal.value
  try {
    let done = ''
    if (kind === 'department') {
      if (editDepartment.value) {
        await api.request(`/departments/${editDepartment.value.id}`, {
          method: 'PATCH',
          body: JSON.stringify({
            expected_revision: editDepartment.value.revision,
            name: depName.value.trim(),
            parent_id: depParent.value || null,
            manager_id: depManager.value || null,
          }),
        })
        done = 'Đã cập nhật phòng ban'
      } else {
        await api.request('/departments', {
          method: 'POST',
          body: JSON.stringify({
            name: depName.value.trim(),
            code: depCode.value.trim(),
            parent_id: depParent.value || null,
            manager_id: depManager.value || null,
          }),
        })
        done = 'Đã thêm phòng ban'
      }
    }
    if (kind === 'user') {
      await api.request('/users', {
        method: 'POST',
        body: JSON.stringify({
          subject: userSubject.value.trim(),
          display_name: userName.value.trim(),
          role: userRole.value,
          department_id: userDepartment.value || null,
        }),
      })
      done = 'Đã thêm thành viên'
    }
    if (kind === 'assign') {
      const person = assignCurrent.value?.display_name ?? 'thành viên'
      await api.request(`/users/${assignUser.value}`, {
        method: 'PATCH',
        body: JSON.stringify({ department_id: assignDepartment.value || null }),
      })
      done = assignDepartment.value
        ? `Đã xếp ${person} vào ${departmentName(assignDepartment.value)}`
        : `Đã đưa ${person} ra khỏi phòng ban`
    }
    toast.success(done)
    modal.value = null
    await Promise.all(
      ['forms', 'users', 'departments'].map((key) => queryClient.invalidateQueries({ queryKey: [key] })),
    )
  } catch (cause) {
    error.value = cause
  } finally {
    busy.value = false
  }
}
</script>
<template>
  <header class="page-head compact">
    <h1 class="sr-only">Thiết lập</h1>
  </header>
  <nav class="subnav settings-tabs" aria-label="Nhóm thiết lập">
    <button
      v-for="item in TABS"
      :key="item.key"
      type="button"
      :class="{ active: tab === item.key }"
      :aria-current="tab === item.key ? 'page' : undefined"
      @click="selectTab(item.key)"
    >
      <component :is="item.icon" :size="16" aria-hidden="true" />{{ item.label }}
    </button>
  </nav>

  <div v-if="tab === 'organization'" class="settings-stack">
    <OrgStats
      v-if="!orgLoading && !orgError"
      :stats="stats"
      :attention-on="attentionOn"
      @unassigned="openUnit(UNASSIGNED_ID)"
      @attention="attentionOn = !attentionOn"
    />
    <section class="card org-card">
      <header class="card-header">
        <div class="org-card-title">
          <h2>Cơ cấu tổ chức</h2>
          <p class="muted">Phòng ban, lãnh đạo và thành viên. Bấm vào một phòng để xem chi tiết và thao tác.</p>
        </div>
        <div class="org-card-actions">
          <div class="org-segmented" role="group" aria-label="Kiểu hiển thị cơ cấu">
            <button
              v-for="item in VIEWS"
              :key="item.key"
              type="button"
              :aria-pressed="orgView === item.key"
              @click="orgView = item.key"
            >
              <component :is="item.icon" :size="16" aria-hidden="true" />{{ item.label }}
            </button>
          </div>
          <template v-if="canManageOrg">
            <button class="button secondary small" type="button" @click="openDepartment()">
              <Plus :size="16" />Thêm phòng ban
            </button>
            <button class="button secondary small" type="button" @click="openUser()">
              <UserPlus :size="16" />Thêm thành viên
            </button>
          </template>
        </div>
      </header>
      <div class="toolbar org-filters">
        <label class="search-box"
          ><Search :size="16" aria-hidden="true" /><input
            v-model="orgQuery"
            type="search"
            placeholder="Tìm phòng ban, mã phòng, tên người…"
            aria-label="Tìm trong cơ cấu tổ chức"
        /></label>
        <label class="org-role-filter">
          <span class="sr-only">Lọc thành viên theo vai trò</span>
          <Filter :size="16" aria-hidden="true" />
          <select v-model="roleFilter" aria-label="Lọc thành viên theo vai trò">
            <option value="">Mọi vai trò</option>
            <option v-for="item in roleOptions" :key="item.key" :value="item.key">{{ item.label }}</option>
          </select>
        </label>
        <button
          class="chip org-attention"
          :class="{ active: attentionOn }"
          type="button"
          :aria-pressed="attentionOn"
          title="Chỉ hiện phòng chưa có lãnh đạo, không có người hoặc lỗi phòng cha"
          @click="attentionOn = !attentionOn"
        >
          <TriangleAlert :size="14" aria-hidden="true" />Cần chú ý
        </button>
        <span v-if="searchSummary" class="org-summary muted" role="status">{{ searchSummary }}</span>
        <button v-if="filtersOn" class="button ghost small" type="button" @click="clearFilters">
          <X :size="16" />Bỏ lọc
        </button>
      </div>

      <StatePanel :loading="orgLoading" :error="orgError" @retry="retryOrg" />
      <template v-if="!orgLoading && !orgError">
        <StatePanel
          v-if="orgView !== 'table' && !tree.byId.size"
          empty
          title="Chưa có phòng ban"
          description="Tạo cơ cấu tổ chức và chỉ định lãnh đạo để quy trình duyệt tìm đúng người."
        >
          <button v-if="canManageOrg" class="button" type="button" @click="openDepartment()">
            <Plus :size="16" />Thêm phòng ban đầu tiên
          </button>
        </StatePanel>
        <OrgChart
          v-else-if="orgView === 'chart'"
          :tree="tree"
          :root-title="rootTitle"
          :query="orgQuery"
          :search="search"
          :attention="attention"
          :selected="drawerTarget"
          @open="openUnit"
        />
        <OrgTreeView
          v-else-if="orgView === 'tree'"
          :tree="tree"
          :root-title="rootTitle"
          :query="orgQuery"
          :search="search"
          :attention="attention"
          :role="roleFilter"
          :selected="drawerTarget"
          @open="openUnit"
        />
        <template v-else>
          <section class="org-table-block" aria-labelledby="org-departments-title">
            <header class="org-table-head">
              <h3 id="org-departments-title">Phòng ban</h3>
              <small class="muted">{{ departmentRows.length }} / {{ tree.byId.size }} phòng</small>
            </header>
            <StatePanel
              compact
              :empty="!departmentRows.length"
              :title="tree.byId.size ? 'Không có phòng ban phù hợp bộ lọc' : 'Chưa có phòng ban'"
              :description="tree.byId.size ? 'Thử bỏ bớt điều kiện lọc.' : 'Tạo cơ cấu tổ chức và chỉ định lãnh đạo cho quy trình duyệt.'"
            />
            <div v-if="departmentRows.length" class="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Phòng ban</th>
                    <th>Mã</th>
                    <th>Lãnh đạo</th>
                    <th>Thành viên</th>
                    <th>Phòng cha</th>
                    <th><span class="sr-only">Thao tác</span></th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="node in departmentRows" :key="node.id">
                    <td>
                      <div class="primary-cell org-indent" :style="{ paddingLeft: `${(node.depth - 1) * 20}px` }">
                        <Building2 :size="18" class="muted" aria-hidden="true" />
                        <div class="org-cell-text">
                          <button class="org-link" type="button" :title="`Mở chi tiết ${node.department.name}`" @click="openUnit(node.id)">
                            <HighlightText :text="node.department.name" :query="orgQuery" />
                          </button>
                          <span v-if="node.warnings.length" class="org-badges">
                            <span
                              v-for="warning in node.warnings"
                              :key="warning"
                              class="org-badge"
                              :class="warning === 'cycle' || warning === 'missing_parent' ? 'danger' : 'warn'"
                              >{{ WARNING_LABELS[warning] }}</span
                            >
                          </span>
                        </div>
                      </div>
                    </td>
                    <td class="mono">{{ node.department.code }}</td>
                    <td>
                      <span v-if="node.leader" class="org-leader-cell"><Crown :size="14" aria-hidden="true" />{{ node.leader.display_name }}</span>
                      <span v-else class="muted">Chưa chỉ định</span>
                    </td>
                    <td class="org-num">
                      {{ node.members.length
                      }}<small v-if="node.totalMembers > node.members.length" class="muted"> / {{ node.totalMembers }} cả khối</small>
                    </td>
                    <td class="muted">{{ departmentName(node.parentId) || '—' }}</td>
                    <td class="org-row-actions">
                      <button
                        v-if="canManageOrg"
                        class="button ghost small"
                        type="button"
                        :aria-label="`Chỉnh sửa ${node.department.name}`"
                        @click="editDep(node.department)"
                      >
                        <Pencil :size="16" />Chỉnh sửa
                      </button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
          <section class="org-table-block" aria-labelledby="org-members-title">
            <header class="org-table-head">
              <h3 id="org-members-title">Thành viên</h3>
              <select v-model="memberDepartment" aria-label="Lọc thành viên theo phòng ban" class="org-select">
                <option value="">Mọi phòng ban</option>
                <option value="none">Chưa xếp phòng</option>
                <option v-for="node in flatten(tree)" :key="node.id" :value="node.id">
                  {{ indented(node) }}
                </option>
              </select>
              <small class="muted">{{ members.length }} / {{ users.data.value?.items.length ?? 0 }} người</small>
            </header>
            <StatePanel
              compact
              :empty="!members.length"
              :title="users.data.value?.items.length ? 'Không có thành viên phù hợp' : 'Chưa có thành viên'"
              :description="users.data.value?.items.length ? 'Thử bỏ bớt điều kiện lọc.' : 'Thêm thành viên để giao việc và duyệt hồ sơ.'"
            />
            <div v-if="members.length" class="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Thành viên</th>
                    <th>Vai trò</th>
                    <th>Phòng ban</th>
                    <th v-if="canManageOrg"><span class="sr-only">Thao tác</span></th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="user in members" :key="user.id">
                    <td>
                      <div class="primary-cell">
                        <span class="avatar" aria-hidden="true"
                          >{{ initialsOf(user.display_name) }}<AvatarPhoto :url="user.avatar_url"
                        /></span>
                        <div>
                          <strong><HighlightText :text="user.display_name" :query="orgQuery" /></strong
                          ><small v-if="user.job_title || user.contact_email">{{
                            [user.job_title, user.contact_email].filter(Boolean).join(' · ')
                          }}</small>
                        </div>
                      </div>
                    </td>
                    <td>{{ roleLabel(user.role) }}</td>
                    <td>
                      <button v-if="user.department_id && tree.byId.has(user.department_id)" class="org-link" type="button" @click="openUnit(user.department_id)">
                        {{ departmentName(user.department_id) }}
                      </button>
                      <span v-else class="muted">{{ user.role === 'director' ? 'Ban giám đốc' : 'Chưa xếp phòng' }}</span>
                    </td>
                    <td v-if="canManageOrg" class="org-row-actions">
                      <button
                        class="button ghost small"
                        type="button"
                        :aria-label="`Chuyển phòng cho ${user.display_name}`"
                        @click="openAssign(user.id, user.department_id ?? null)"
                      >
                        <ArrowRightLeft :size="16" />Chuyển phòng
                      </button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
        </template>
      </template>
    </section>
  </div>

  <div v-if="tab === 'audit'" class="settings-stack"><AuditLog /></div>
  <div v-if="tab === 'permissions'" class="settings-stack">
    <RoleMatrix v-if="session.can('organization.manage')" @dirty="matrixDirty = $event" />
    <section class="card">
      <header class="card-header">
        <div class="settings-card-title">
          <h2>Quyền của bạn</h2>
          <p class="muted">Máy chủ vẫn kiểm tra quyền ở từng tài nguyên và thao tác.</p>
        </div>
        <ShieldCheck :size="24" class="settings-accent" aria-hidden="true" />
      </header>
      <div class="card-body settings-own">
        <dl class="detail-meta settings-own-meta">
          <div>
            <dt>Tài khoản</dt>
            <dd>{{ session.user?.display_name }}</dd>
          </div>
          <div>
            <dt>Mẫu vai trò</dt>
            <dd>{{ roleLabel(session.user?.role) }}</dd>
          </div>
        </dl>
        <ul v-if="session.user?.capabilities?.length" class="settings-capabilities">
          <li v-for="capability in session.user?.capabilities" :key="capability">
            <Check :size="16" class="settings-accent" aria-hidden="true" />
            <div>
              <strong>{{ permissionLabel(capability) }}</strong
              ><small v-if="PERMISSIONS[capability]">{{ PERMISSIONS[capability].hint }}</small>
            </div>
          </li>
        </ul>
        <p v-else class="muted">Quyền được kiểm tra theo hành động trên từng tài nguyên.</p>
        <div class="notice warning">
          Quản trị kỹ thuật không đồng nghĩa với quyền đọc mọi hồ sơ. Quyền nội dung được cấp riêng theo tài nguyên và
          nghiệp vụ.
        </div>
      </div>
    </section>
  </div>

  <OrgDrawer
    v-if="drawerTarget && tab === 'organization'"
    :tree="tree"
    :target="drawerTarget"
    :root-title="rootTitle"
    :role="roleFilter"
    :can-manage="canManageOrg"
    @close="drawerTarget = null"
    @open="openUnit"
    @edit="editById"
    @add-member="openUser"
    @assign="openAssign"
    @add-child="openDepartment"
  />

  <ModalDialog v-if="modal" :title="modalTitle" @close="closeModal">
    <div v-if="error" class="notice error settings-error" role="alert">
      <div>
        {{ errorText(error) }}<code v-if="error instanceof ApiError && error.traceId">{{ error.traceId }}</code>
      </div>
    </div>
    <form novalidate @submit.prevent="save">
      <div class="settings-form">
        <template v-if="modal === 'department'">
          <div class="field">
            <label for="dep-name">Tên phòng ban <span class="required" aria-hidden="true">*</span></label>
            <input id="dep-name" v-model="depName" required maxlength="200" autocomplete="off" />
          </div>
          <div v-if="!editDepartment" class="field">
            <label for="dep-code">Mã phòng ban <span class="required" aria-hidden="true">*</span></label>
            <input
              id="dep-code"
              v-model="depCode"
              class="mono"
              required
              maxlength="50"
              autocomplete="off"
              :aria-invalid="codeTaken"
              aria-describedby="dep-code-hint"
            />
            <small v-if="codeTaken" id="dep-code-hint" class="field-error">Mã này đã được phòng ban khác dùng.</small>
            <small v-else id="dep-code-hint">Mã ngắn, không đổi được sau khi tạo. Ví dụ: KT, HC.</small>
          </div>
          <div class="field">
            <label for="dep-parent">Phòng cha</label>
            <select id="dep-parent" v-model="depParent" aria-describedby="dep-parent-hint">
              <option value="">Không có (trực thuộc tổ chức)</option>
              <option v-for="item in parentChoices" :key="item.id" :value="item.id" :disabled="item.disabled">
                {{ item.label + item.reason }}
              </option>
            </select>
            <small id="dep-parent-hint">Không chọn được chính phòng này hoặc phòng con của nó, để cây không bị vòng lặp.</small>
          </div>
          <div class="field">
            <label for="dep-manager">Lãnh đạo phòng</label>
            <select id="dep-manager" v-model="depManager">
              <option value="">Chưa chỉ định</option>
              <template v-for="group in managerGroups" :key="group.label">
                <optgroup v-if="group.label" :label="group.label">
                  <option v-for="user in group.people" :key="user.id" :value="user.id">{{ user.display_name }}</option>
                </optgroup>
                <template v-else>
                  <option v-for="user in group.people" :key="user.id" :value="user.id">{{ user.display_name }}</option>
                </template>
              </template>
            </select>
          </div>
        </template>
        <template v-if="modal === 'user'">
          <div class="notice warning">
            Tạo tài khoản đăng nhập trước (trong hệ thống đăng nhập một lần), rồi dán mã tài khoản vào đây để nối với hồ sơ
            thành viên. Thao tác này không tạo mật khẩu.
          </div>
          <div class="field">
            <label for="user-subject">Mã tài khoản đăng nhập <span class="required" aria-hidden="true">*</span></label>
            <input
              id="user-subject"
              v-model="userSubject"
              class="mono"
              required
              maxlength="200"
              autocomplete="off"
              placeholder="UUID trong Keycloak"
              :aria-invalid="subjectTaken"
              aria-describedby="user-subject-hint"
            />
            <small v-if="subjectTaken" id="user-subject-hint" class="field-error">Mã tài khoản này đã gắn với một thành viên.</small>
          </div>
          <div class="field">
            <label for="user-name">Tên hiển thị <span class="required" aria-hidden="true">*</span></label>
            <input id="user-name" v-model="userName" required maxlength="200" autocomplete="off" />
          </div>
          <div class="field">
            <label for="user-role">Vai trò</label>
            <select id="user-role" v-model="userRole">
              <option v-for="(label, role) in ROLE_LABELS" :key="role" :value="role">{{ label }}</option>
            </select>
          </div>
          <div class="field">
            <label for="user-department">Phòng ban</label>
            <select id="user-department" v-model="userDepartment">
              <option value="">Chưa xếp phòng</option>
              <option v-for="node in flatten(tree)" :key="node.id" :value="node.id">
                {{ indented(node) }}
              </option>
            </select>
          </div>
        </template>
        <template v-if="modal === 'assign'">
          <div class="field">
            <label for="assign-user">Thành viên</label>
            <select id="assign-user" v-model="assignUser">
              <option value="" disabled>Chọn người…</option>
              <option v-for="user in users.data.value?.items" :key="user.id" :value="user.id">
                {{ user.display_name }} — {{ departmentName(user.department_id) || 'chưa xếp phòng' }}
              </option>
            </select>
          </div>
          <div class="field">
            <label for="assign-department">Chuyển vào phòng</label>
            <select id="assign-department" v-model="assignDepartment" aria-describedby="assign-hint">
              <option value="">Không thuộc phòng nào</option>
              <option v-for="node in flatten(tree)" :key="node.id" :value="node.id">
                {{ indented(node) }}
              </option>
            </select>
            <small id="assign-hint">Vai trò và quyền của người này giữ nguyên; chỉ phòng ban thay đổi.</small>
          </div>
        </template>
      </div>
      <div class="form-actions">
        <button type="button" class="button secondary" :disabled="busy" @click="closeModal">Hủy</button>
        <button class="button" type="submit" :disabled="busy || !!blocker" :title="blocker || undefined" :aria-busy="busy">
          <Save :size="16" />{{ busy ? 'Đang lưu…' : 'Lưu' }}
        </button>
      </div>
      <p v-if="blocker && !busy" class="settings-blocker muted" aria-live="polite">{{ blocker }}.</p>
    </form>
  </ModalDialog>
</template>
<style scoped>
/* ---- Tabs: icon and label never touch; a phone scrolls the row instead of wrapping it. ---- */
.settings-tabs {
  gap: 24px;
  overflow-x: auto;
  scrollbar-width: none;
}
.settings-tabs::-webkit-scrollbar {
  display: none;
}
.settings-tabs button {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex: none;
  min-height: 44px;
  padding: 8px 2px 12px;
  white-space: nowrap;
  transition:
    color 0.15s,
    border-color 0.15s;
}
.settings-tabs button:hover {
  color: var(--navy);
}
.settings-tabs button.active:hover {
  color: var(--teal);
}
.settings-stack {
  display: grid;
  gap: 24px;
}

/* ---- Organisation card ---- */
.org-card-title {
  display: grid;
  gap: 4px;
  min-width: 0;
  flex: 1 1 280px;
}
.org-card-title p {
  font-size: 0.875rem;
  line-height: 1.5;
}
.org-card-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
.org-card-actions .org-segmented {
  margin-right: 8px;
}
.org-filters {
  justify-content: flex-start;
  flex-wrap: wrap;
  gap: 12px;
  padding: 16px 24px;
}
.org-filters .search-box {
  flex: 1 1 260px;
  max-width: 420px;
}
.org-role-filter {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--muted);
}
.org-role-filter select,
.org-select {
  width: auto;
  min-width: 180px;
  min-height: 40px;
  font-size: 0.875rem;
}
.org-attention {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.org-summary {
  font-size: 0.875rem;
}
.org-table-block + .org-table-block {
  border-top: 1px solid var(--border);
}
.org-table-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  padding: 16px 24px;
}
.org-table-head h3 {
  margin-right: auto;
  font-size: 1rem;
}
.org-cell-text {
  display: grid;
  gap: 6px;
  min-width: 0;
}
.org-link {
  padding: 0;
  border: 0;
  background: none;
  color: var(--navy);
  font-weight: 600;
  text-align: left;
  font-size: inherit;
}
.org-link:hover {
  color: var(--teal);
  text-decoration: underline;
}
.org-leader-cell {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.org-leader-cell svg {
  color: var(--amber-ink);
}
.org-num {
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.org-row-actions {
  text-align: right;
  white-space: nowrap;
}

/* ---- Permissions tab ---- */
.settings-card-title {
  display: grid;
  gap: 4px;
}
.settings-card-title p {
  font-size: 0.875rem;
}
.settings-accent {
  flex: none;
  color: var(--teal);
}
.settings-own {
  display: grid;
  gap: 24px;
}
.settings-capabilities {
  display: grid;
  margin: 0;
  padding: 0;
  list-style: none;
}
.settings-capabilities li {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 0;
  border-bottom: 1px solid var(--border-soft);
}
.settings-capabilities li:last-child {
  border-bottom: 0;
}
.settings-capabilities li svg {
  margin-top: 3px;
}
.settings-capabilities strong {
  display: block;
  font-weight: 600;
}
.settings-capabilities small {
  display: block;
  margin-top: 4px;
  color: var(--muted);
  font-size: 0.875rem;
  line-height: 1.45;
}

/* ---- Dialog form: label → control 6px (from .field), field → field 16px, notice 16px apart ---- */
.settings-form {
  display: grid;
  gap: 16px;
}
.settings-form .field {
  gap: 6px;
}
.settings-error {
  margin-bottom: 16px;
}
.settings-blocker {
  margin: 8px 0 0;
  text-align: right;
  font-size: 0.8125rem;
}

@media (max-width: 640px) {
  .settings-tabs {
    gap: 16px;
  }
  .settings-stack {
    gap: 16px;
  }
  .org-filters,
  .org-table-head {
    padding: 12px 16px;
  }
  .org-filters .search-box {
    max-width: none;
  }
  .org-role-filter,
  .org-role-filter select {
    flex: 1;
  }
  .org-card-actions {
    width: 100%;
  }
  .org-card-actions .org-segmented {
    width: 100%;
    margin-right: 0;
  }
  .org-card-actions .org-segmented button {
    flex: 1;
    justify-content: center;
  }
  .org-card-actions > .button {
    flex: 1;
  }
}
</style>
