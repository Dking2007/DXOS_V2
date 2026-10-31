<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import {
  Building2,
  Check,
  Plus,
  Save,
  ShieldCheck,
  UserPlus,
} from 'lucide-vue-next'
import { api } from '../api'
import { useSession } from '../stores/session'
import { ApiError, errorText } from '@dx/web-shared/api.ts'
import type { Page } from '@dx/web-shared/api.ts'
import type {
  Department,
  User,
} from '@dx/web-shared/types.ts'
import StatePanel from '@dx/web-shared/components/StatePanel.vue'
import ModalDialog from '@dx/web-shared/components/ModalDialog.vue'
import RoleMatrix from '../components/RoleMatrix.vue'
import AppearanceSettings from '../components/AppearanceSettings.vue'
import AuditLog from '../components/AuditLog.vue'
import { permissionLabel, PERMISSIONS, roleLabel } from '../ui/labels'
import { toast } from '../ui/toast'
import { confirmDiscard } from '../ui/unsaved'
const session = useSession()
const queryClient = useQueryClient()
type SettingsTab = 'organization' | 'permissions' | 'audit' | 'appearance'
const requestedTab = String(useRoute().query.tab ?? '')
// Forms and their approval steps are designed on the process screen now.
if (requestedTab === 'forms') void useRouter().replace('/packages')
const tab = ref<SettingsTab>(
  (['organization', 'permissions', 'audit', 'appearance'] as const).find(
    (key) => key === requestedTab && (key !== 'audit' || session.can('audit.read')),
  ) ??
    (['director', 'manager'].includes(session.user?.role ?? '') ? 'organization' : 'permissions'),
)
const users = useQuery({
  queryKey: ['users'],
  queryFn: () => api.request<Page<User>>('/users'),
})
const departments = useQuery({
  queryKey: ['departments'],
  queryFn: () => api.request<Page<Department>>('/departments'),
})
const canManageOrg = computed(() =>
  ['director', 'technical_admin'].includes(session.user?.role ?? ''),
)
const modal = ref<'department' | 'user' | null>(null)
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
const opened = ref('')
function modalState() {
  if (modal.value === 'department') return JSON.stringify([depName.value, depCode.value, depParent.value, depManager.value])
  if (modal.value === 'user') return JSON.stringify([userSubject.value, userName.value, userRole.value, userDepartment.value])
  return ''
}
function closeModal() {
  if (busy.value) return
  if (confirmDiscard(modalState() !== opened.value)) modal.value = null
}
function open(type: typeof modal.value) {
  modal.value = type
  error.value = null
  if (type === 'department') {
    editDepartment.value = null
    depName.value = ''
    depCode.value = ''
    depParent.value = ''
    depManager.value = ''
  }
  opened.value = modalState()
}
function editDep(item: Department) {
  open('department')
  editDepartment.value = item
  depName.value = item.name
  depCode.value = item.code ?? ''
  depParent.value = item.parent_id ?? ''
  depManager.value = item.manager_id ?? ''
  opened.value = modalState()
}
async function save() {
  busy.value = true
  error.value = null
  try {
    if (modal.value === 'department') {
      if (editDepartment.value)
        await api.request(`/departments/${editDepartment.value.id}`, {
          method: 'PATCH',
          body: JSON.stringify({
            expected_revision: editDepartment.value.revision,
            name: depName.value,
            parent_id: depParent.value || null,
            manager_id: depManager.value || null,
          }),
        })
      else
        await api.request('/departments', {
          method: 'POST',
          body: JSON.stringify({
            name: depName.value,
            code: depCode.value,
            parent_id: depParent.value || null,
            manager_id: depManager.value || null,
          }),
        })
    }
    if (modal.value === 'user')
      await api.request('/users', {
        method: 'POST',
        body: JSON.stringify({
          subject: userSubject.value,
          display_name: userName.value,
          role: userRole.value,
          department_id: userDepartment.value || null,
        }),
      })
    toast.success(
      modal.value === 'user'
          ? 'Đã thêm thành viên'
          : editDepartment.value
            ? 'Đã cập nhật phòng ban'
            : 'Đã thêm phòng ban',
    )
    modal.value = null
    await Promise.all(
      ['forms', 'users', 'departments'].map((key) =>
        queryClient.invalidateQueries({ queryKey: [key] }),
      ),
    )
  } catch (cause) {
    error.value = cause
  } finally {
    busy.value = false
  }
}
const roleLabels: Record<string, string> = {
  director: roleLabel('director'),
  manager: roleLabel('manager'),
  staff: roleLabel('staff'),
  technical_admin: roleLabel('technical_admin'),
}
</script>
<template>
  <header class="page-head">
    <div>
      <span class="eyebrow">CẤU HÌNH NGHIỆP VỤ</span>
      <h1>Thiết lập không gian</h1>
      <p>Cơ cấu tổ chức, vai trò và quyền, nhật ký. Biểu mẫu và bước duyệt thiết kế ở màn Quy trình.</p>
    </div>
  </header>
  <nav class="subnav" aria-label="Nhóm thiết lập">
    <button
      :class="{ active: tab === 'organization' }"
      @click="tab = 'organization'"
    >
      Cơ cấu tổ chức</button
    ><button
      :class="{ active: tab === 'permissions' }"
      @click="tab = 'permissions'"
    >
      Vai trò & quyền</button
    ><button
      v-if="session.can('audit.read')"
      :class="{ active: tab === 'audit' }"
      @click="tab = 'audit'"
    >
      Nhật ký hoạt động</button
    ><button
      :class="{ active: tab === 'appearance' }"
      @click="tab = 'appearance'"
    >
      Giao diện
    </button>
  </nav>
  <template v-if="tab === 'organization'"
    ><div class="stack">
      <section class="card">
        <header class="card-header">
          <h2>Phòng ban</h2>
          <button
            v-if="canManageOrg"
            class="button secondary small"
            @click="open('department')"
          >
            <Plus :size="16" />Thêm phòng ban
          </button>
        </header>
        <StatePanel
          :loading="departments.isPending.value"
          :error="departments.error.value"
          :empty="departments.data.value?.items.length === 0"
          title="Chưa có phòng ban"
          description="Tạo cơ cấu tổ chức và chỉ định lãnh đạo cho quy trình duyệt."
          @retry="departments.refetch()"
        />
        <div v-if="departments.data.value?.items.length" class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Phòng ban</th>
                <th>Mã</th>
                <th>Lãnh đạo</th>
                <th>Phòng cha</th>
                <th />
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="department in departments.data.value.items"
                :key="department.id"
              >
                <td>
                  <div class="primary-cell">
                    <Building2 :size="18" class="muted" /><strong>{{
                      department.name
                    }}</strong>
                  </div>
                </td>
                <td class="mono">{{ department.code }}</td>
                <td>
                  {{
                    users.data.value?.items.find(
                      (user) => user.id === department.manager_id,
                    )?.display_name || 'Chưa chỉ định'
                  }}
                </td>
                <td class="muted">
                  {{
                    departments.data.value.items.find(
                      (item) => item.id === department.parent_id,
                    )?.name || '—'
                  }}
                </td>
                <td>
                  <button
                    v-if="canManageOrg"
                    class="button ghost small"
                    @click="editDep(department)"
                  >
                    Chỉnh sửa
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
      <section class="card">
        <header class="card-header">
          <h2>Thành viên</h2>
          <button
            v-if="canManageOrg"
            class="button secondary small"
            @click="open('user')"
          >
            <UserPlus :size="16" />Thêm hồ sơ thành viên
          </button>
        </header>
        <StatePanel
          :loading="users.isPending.value"
          :error="users.error.value"
          :empty="users.data.value?.items.length === 0"
          title="Chưa có thành viên"
          @retry="users.refetch()"
        />
        <div v-if="users.data.value?.items.length" class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Thành viên</th>
                <th>Vai trò</th>
                <th>Phòng ban</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="user in users.data.value.items" :key="user.id">
                <td>
                  <div class="primary-cell">
                    <span class="avatar">{{
                      user.display_name.split(' ').slice(-1)[0]?.slice(0, 1)
                    }}</span>
                    <div>
                      <strong>{{ user.display_name }}</strong
                      ><small class="mono">{{
                        user.subject.slice(0, 18)
                      }}</small>
                    </div>
                  </div>
                </td>
                <td>{{ roleLabels[user.role || 'staff'] || user.role }}</td>
                <td class="muted">
                  {{
                    departments.data.value?.items.find(
                      (item) => item.id === user.department_id,
                    )?.name || 'Chưa phân phòng'
                  }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div></template
  >
  <template v-if="tab === 'audit'"><AuditLog /></template>
  <template v-if="tab === 'appearance'"><div class="stack"><AppearanceSettings /></div></template>
  <template v-if="tab === 'permissions'"
    ><RoleMatrix v-if="session.can('organization.manage')" style="margin-bottom: 20px" /><section class="card">
      <header class="card-header">
        <div>
          <h2>Quyền của bạn</h2>
          <p class="muted" style="font-size: 13px; margin-top: 5px">
            Máy chủ vẫn kiểm tra quyền ở từng tài nguyên và thao tác.
          </p>
        </div>
        <ShieldCheck :size="23" style="color: var(--teal)" />
      </header>
      <div class="card-body">
        <dl class="detail-meta" style="margin-bottom: 23px">
          <div>
            <dt>Tài khoản</dt>
            <dd>{{ session.user?.display_name }}</dd>
          </div>
          <div>
            <dt>Mẫu vai trò</dt>
            <dd>{{ roleLabels[session.user?.role || 'staff'] }}</dd>
          </div>
        </dl>
        <div
          v-for="capability in session.user?.capabilities"
          :key="capability"
          class="list-row"
          style="padding: 11px 0"
        >
          <Check :size="16" style="color: var(--teal)" />
          <div class="grow">
            <strong>{{ permissionLabel(capability) }}</strong
            ><small v-if="PERMISSIONS[capability]">{{ PERMISSIONS[capability].hint }}</small>
          </div>
        </div>
        <p v-if="!session.user?.capabilities?.length" class="muted">
          Quyền được kiểm tra theo hành động trên từng tài nguyên.
        </p>
        <div class="notice warning" style="margin-top: 22px">
          Quản trị kỹ thuật không đồng nghĩa với quyền đọc mọi hồ sơ. Quyền nội
          dung được cấp riêng theo tài nguyên và nghiệp vụ.
        </div>
      </div>
    </section></template
  >
  <ModalDialog
    v-if="modal"
    :title="
      modal === 'department'
        ? editDepartment
          ? 'Cập nhật phòng ban'
          : 'Thêm phòng ban'
        : 'Thêm hồ sơ thành viên'
    "
    @close="closeModal"
  >
    <div v-if="error" class="notice error error-inline" role="alert">
      <div>
        {{ errorText(error)
        }}<code v-if="error instanceof ApiError && error.traceId">{{
          error.traceId
        }}</code>
      </div>
    </div>
    <form @submit.prevent="save">
      <div class="stack">
        <template v-if="modal === 'department'"
          ><div class="field">
            <label for="dep-name">Tên phòng ban</label
            ><input id="dep-name" v-model="depName" required />
          </div>
          <div v-if="!editDepartment" class="field">
            <label for="dep-code">Mã phòng ban</label
            ><input id="dep-code" v-model="depCode" required />
          </div>
          <div class="field">
            <label for="dep-parent">Phòng cha</label
            ><select id="dep-parent" v-model="depParent">
              <option value="">Không có / cấp tổ chức</option>
              <option
                v-for="department in departments.data.value?.items.filter(
                  (item) => item.id !== editDepartment?.id,
                )"
                :key="department.id"
                :value="department.id"
              >
                {{ department.name }}
              </option>
            </select>
          </div>
          <div class="field">
            <label for="dep-manager">Lãnh đạo phòng</label
            ><select id="dep-manager" v-model="depManager">
              <option value="">Chưa chỉ định</option>
              <option
                v-for="user in users.data.value?.items"
                :key="user.id"
                :value="user.id"
              >
                {{ user.display_name }}
              </option>
            </select>
          </div></template
        >
        <template v-if="modal === 'user'"
          ><div class="notice warning">
            Tạo tài khoản đăng nhập trước (trong hệ thống đăng nhập một lần), rồi
            dán mã tài khoản vào đây để nối với hồ sơ thành viên. Thao tác này không tạo mật khẩu.
          </div>
          <div class="field">
            <label for="user-subject">Mã tài khoản đăng nhập</label
            ><input
              id="user-subject"
              v-model="userSubject"
              class="mono"
              required
              placeholder="UUID trong Keycloak"
            />
          </div>
          <div class="field">
            <label for="user-name">Tên hiển thị</label
            ><input id="user-name" v-model="userName" required />
          </div>
          <div class="field">
            <label for="user-role">Vai trò</label
            ><select id="user-role" v-model="userRole">
              <option
                v-for="(label, role) in roleLabels"
                :key="role"
                :value="role"
              >
                {{ label }}
              </option>
            </select>
          </div>
          <div class="field">
            <label for="user-department">Phòng ban</label
            ><select id="user-department" v-model="userDepartment">
              <option value="">Chưa phân phòng</option>
              <option
                v-for="department in departments.data.value?.items"
                :key="department.id"
                :value="department.id"
              >
                {{ department.name }}
              </option>
            </select>
          </div></template
        >
      </div>
      <div class="form-actions">
        <button
          type="button"
          class="button secondary"
          :disabled="busy"
          @click="closeModal"
        >
          Hủy</button
        ><button class="button" :disabled="busy">
          <Save :size="16" />{{
            busy ? 'Đang lưu…' : 'Lưu'
          }}
        </button>
      </div>
    </form>
  </ModalDialog>
</template>
