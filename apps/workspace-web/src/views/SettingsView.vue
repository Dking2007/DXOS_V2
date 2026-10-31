<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import {
  ArrowDown,
  ArrowUp,
  Building2,
  Check,
  FilePlus2,
  Plus,
  Save,
  ShieldCheck,
  Trash2,
  UserPlus,
  Workflow,
} from 'lucide-vue-next'
import { api } from '../api'
import { useSession } from '../stores/session'
import { ApiError, errorText } from '@dx/web-shared/api.ts'
import type { Page } from '@dx/web-shared/api.ts'
import type {
  ApprovalStep,
  Department,
  FormField,
  FormTemplate,
  User,
} from '@dx/web-shared/types.ts'
import { fieldKey } from '@dx/web-shared/forms.ts'
import StatePanel from '@dx/web-shared/components/StatePanel.vue'
import ModalDialog from '@dx/web-shared/components/ModalDialog.vue'
import SchemaForm from '@dx/web-shared/components/SchemaForm.vue'
import StatusBadge from '@dx/web-shared/components/StatusBadge.vue'
import RoleMatrix from '../components/RoleMatrix.vue'
import AppearanceSettings from '../components/AppearanceSettings.vue'
import AuditLog from '../components/AuditLog.vue'
import { permissionLabel, PERMISSIONS, roleLabel } from '../ui/labels'
import { toast } from '../ui/toast'
import { confirmDiscard } from '../ui/unsaved'
const session = useSession()
const queryClient = useQueryClient()
type SettingsTab = 'forms' | 'organization' | 'permissions' | 'audit' | 'appearance'
const requestedTab = String(useRoute().query.tab ?? '')
const tab = ref<SettingsTab>(
  (['forms', 'organization', 'permissions', 'audit', 'appearance'] as const).find(
    (key) => key === requestedTab && (key !== 'audit' || session.can('audit.read')),
  ) ??
    (['director', 'manager'].includes(session.user?.role ?? '') ? 'forms' : 'permissions'),
)
const forms = useQuery({
  queryKey: ['forms'],
  queryFn: () => api.request<Page<FormTemplate>>('/forms'),
})
const users = useQuery({
  queryKey: ['users'],
  queryFn: () => api.request<Page<User>>('/users'),
})
const departments = useQuery({
  queryKey: ['departments'],
  queryFn: () => api.request<Page<Department>>('/departments'),
})
const isDesigner = computed(() =>
  ['director', 'manager'].includes(session.user?.role ?? ''),
)
const canManageOrg = computed(() =>
  ['director', 'technical_admin'].includes(session.user?.role ?? ''),
)
const modal = ref<'form' | 'department' | 'user' | 'preview' | null>(null)
const error = ref<unknown>(null)
const busy = ref(false)
const formName = ref('')
const description = ref('')
const fields = ref<FormField[]>([])
const steps = ref<ApprovalStep[]>([])
const preview = ref<FormTemplate | null>(null)
const previewPayload = ref<Record<string, unknown>>({})
const depName = ref('')
const depCode = ref('')
const depParent = ref('')
const depManager = ref('')
const editDepartment = ref<Department | null>(null)
const userSubject = ref('')
const userName = ref('')
const userRole = ref('staff')
const userDepartment = ref('')
const builderError = ref('')
const opened = ref('')
function modalState() {
  if (modal.value === 'form') return JSON.stringify([formName.value, description.value, fields.value, steps.value])
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
  builderError.value = ''
  if (type === 'form') {
    formName.value = ''
    description.value = ''
    fields.value = []
    steps.value = [
      { label: 'Lãnh đạo phòng phê duyệt', resolver: 'department_manager' },
    ]
  }
  if (type === 'department') {
    editDepartment.value = null
    depName.value = ''
    depCode.value = ''
    depParent.value = ''
    depManager.value = ''
  }
  opened.value = modalState()
}
function addField() {
  fields.value.push({
    key: `truong_${fields.value.length + 1}`,
    label: '',
    type: 'text',
    required: false,
  })
}
function autoKey(field: FormField) {
  if (/^truong_\d+$/.test(field.key) || !field.key)
    field.key = fieldKey(field.label)
}
function setOptions(field: FormField, event: Event) {
  field.options = (event.target as HTMLInputElement).value
    .split(',')
    .map((value) => value.trim())
    .filter(Boolean)
}
function moveField(index: number, change: number) {
  const other = index + change
  if (other < 0 || other >= fields.value.length) return
  ;[fields.value[index], fields.value[other]] = [
    fields.value[other]!,
    fields.value[index]!,
  ]
}
function previewForm(item: FormTemplate) {
  preview.value = item
  previewPayload.value = {}
  modal.value = 'preview'
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
  if (modal.value === 'form') {
    if (!fields.value.length) {
      builderError.value = 'Thêm ít nhất một trường thông tin.'
      return
    }
    if (
      new Set(fields.value.map((field) => field.key)).size !==
      fields.value.length
    ) {
      builderError.value = 'Có hai trường trùng mã. Đổi tên hoặc mã của một trường.'
      return
    }
    if (!steps.value.length) {
      builderError.value = 'Thêm ít nhất một bước phê duyệt.'
      return
    }
  }
  busy.value = true
  error.value = null
  try {
    if (modal.value === 'form')
      await api.request('/forms', {
        method: 'POST',
        body: JSON.stringify({
          name: formName.value,
          description: description.value,
          fields: fields.value,
          approval_steps: steps.value,
        }),
      })
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
      modal.value === 'form'
        ? 'Đã tạo mẫu hồ sơ'
        : modal.value === 'user'
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
      <p>Biểu mẫu, người nhận và cơ cấu làm việc của tổ chức.</p>
    </div>
  </header>
  <nav class="subnav" aria-label="Nhóm thiết lập">
    <button :class="{ active: tab === 'forms' }" @click="tab = 'forms'">
      Biểu mẫu & quy trình</button
    ><button
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
  <template v-if="tab === 'forms'"
    ><section class="card">
      <header class="card-header">
        <div>
          <h2>Mẫu hồ sơ đã phát hành</h2>
          <p class="muted" style="font-size: 13px; margin-top: 5px">
            Mỗi mẫu giữ nguyên cấu trúc và quy trình khi được sử dụng.
          </p>
        </div>
        <button v-if="isDesigner" class="button" @click="open('form')">
          <FilePlus2 :size="17" />Tạo mẫu hồ sơ
        </button>
      </header>
      <StatePanel
        :loading="forms.isPending.value"
        :error="forms.error.value"
        :empty="forms.data.value?.items.length === 0"
        title="Chưa có mẫu hồ sơ"
        description="Thiết kế trường thông tin và người duyệt để cán bộ có thể tạo hồ sơ đúng chuẩn."
        @retry="forms.refetch()"
        ><button v-if="isDesigner" class="button small" @click="open('form')">
          Tạo mẫu đầu tiên
        </button></StatePanel
      >
      <div
        v-for="form in forms.data.value?.items"
        :key="form.id"
        class="list-row"
      >
        <span class="file-icon"><Workflow :size="20" /></span>
        <div class="grow">
          <p>{{ form.name }}</p>
          <small
            >{{ form.fields.length }} trường thông tin ·
            {{ form.approval_steps.length }} bước duyệt ·
            {{ form.description || 'Chưa có mô tả' }}</small
          >
        </div>
        <StatusBadge :status="form.state || 'published'" /><button
          class="button secondary small"
          @click="previewForm(form)"
        >
          Xem mẫu
        </button>
      </div>
    </section>
    <div class="intro-strip">
      <ShieldCheck :size="25" />
      <p>
        <strong>Phát hành là một cam kết cấu trúc.</strong> Mẫu đã phát hành
        không bị sửa ngầm. Để thay đổi nghiệp vụ, tạo mẫu mới; hồ sơ cũ tiếp tục
        giữ cấu trúc đã chọn.
      </p>
    </div></template
  >
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
      modal === 'form'
        ? 'Thiết kế mẫu hồ sơ'
        : modal === 'department'
          ? editDepartment
            ? 'Cập nhật phòng ban'
            : 'Thêm phòng ban'
          : modal === 'user'
            ? 'Thêm hồ sơ thành viên'
            : preview?.name || 'Xem biểu mẫu'
    "
    :wide="modal === 'form' || modal === 'preview'"
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
    <div v-if="builderError" class="notice error error-inline" role="alert">
      {{ builderError }}
    </div>
    <template v-if="modal === 'preview' && preview"
      ><p class="muted" style="margin-bottom: 22px">
        {{ preview.description }}
      </p>
      <SchemaForm v-model="previewPayload" :fields="preview.fields" />
      <hr class="divider" />
      <h3>Quy trình phê duyệt</h3>
      <div
        v-for="(step, index) in preview.approval_steps"
        :key="index"
        class="list-row"
        style="padding: 12px 0"
      >
        <span class="rail-circle">{{ index + 1 }}</span>
        <div class="grow">
          <p>{{ step.label }}</p>
          <small>{{
            step.resolver === 'department_manager'
              ? 'Lãnh đạo phòng người gửi'
              : users.data.value?.items.find((user) => user.id === step.user_id)
                  ?.display_name || 'Người được chỉ định'
          }}</small
          ><small v-if="step.condition"
            >Điều kiện: {{ step.condition.field }} {{ step.condition.operator }}
            {{ step.condition.value }}</small
          >
        </div>
      </div></template
    >
    <form v-else @submit.prevent="save">
      <div class="stack">
        <template v-if="modal === 'form'"
          ><div class="form-grid">
            <div class="field full-width">
              <label for="template-name">Tên mẫu hồ sơ</label
              ><input
                id="template-name"
                v-model="formName"
                required
                maxlength="255"
                placeholder="Ví dụ: Đề nghị phê duyệt kế hoạch"
              />
            </div>
            <div class="field full-width">
              <label for="template-description">Mô tả</label
              ><textarea
                id="template-description"
                v-model="description"
                rows="2"
                placeholder="Mẫu này dùng khi nào?"
              />
            </div>
          </div>
          <div>
            <div class="card-header" style="padding: 0 0 15px; border: 0">
              <h3>Trường thông tin</h3>
              <button
                type="button"
                class="button secondary small"
                @click="addField"
              >
                <Plus :size="15" />Thêm trường
              </button>
            </div>
            <div v-if="!fields.length" class="notice">
              Thêm các trường để người tạo hồ sơ nhập đúng thông tin cần thiết.
            </div>
            <div
              v-for="(field, index) in fields"
              :key="index"
              class="builder-field"
            >
              <div class="builder-field-head">
                <span>TRƯỜNG {{ index + 1 }}</span>
                <div class="inline-actions">
                  <button
                    type="button"
                    class="icon-button"
                    aria-label="Chuyển trường lên"
                    :disabled="index === 0"
                    @click="moveField(index, -1)"
                  >
                    <ArrowUp :size="14" /></button
                  ><button
                    type="button"
                    class="icon-button"
                    aria-label="Chuyển trường xuống"
                    :disabled="index === fields.length - 1"
                    @click="moveField(index, 1)"
                  >
                    <ArrowDown :size="14" /></button
                  ><button
                    type="button"
                    class="icon-button"
                    aria-label="Xóa trường"
                    @click="fields.splice(index, 1)"
                  >
                    <Trash2 :size="15" />
                  </button>
                </div>
              </div>
              <div class="form-grid" style="gap: 12px">
                <div class="field">
                  <label :for="`label-${index}`">Nhãn hiển thị</label
                  ><input
                    :id="`label-${index}`"
                    v-model="field.label"
                    required
                    @blur="autoKey(field)"
                  />
                </div>
                <div class="field">
                  <label :for="`type-${index}`">Loại trường</label
                  ><select :id="`type-${index}`" v-model="field.type">
                    <option value="text">Văn bản ngắn</option>
                    <option value="textarea">Văn bản nhiều dòng</option>
                    <option value="number">Số / số tiền</option>
                    <option value="date">Ngày</option>
                    <option value="select">Chọn một giá trị</option>
                    <option value="checkbox">Xác nhận / checkbox</option>
                  </select>
                </div>
                <div class="field">
                  <label :for="`key-${index}`">Mã trường (tự tạo từ tên, không dấu)</label
                  ><input
                    :id="`key-${index}`"
                    v-model="field.key"
                    required
                    pattern="[a-z][a-z0-9_]*"
                    class="mono"
                  />
                </div>
                <div v-if="field.type === 'select'" class="field">
                  <label :for="`options-${index}`"
                    >Các lựa chọn, cách bằng dấu phẩy</label
                  ><input
                    :id="`options-${index}`"
                    :value="field.options?.join(', ')"
                    required
                    @input="setOptions(field, $event)"
                  />
                </div>
              </div>
              <label class="checkbox-label"
                ><input v-model="field.required" type="checkbox" />Bắt buộc
                điền</label
              >
            </div>
          </div>
          <div>
            <div class="card-header" style="padding: 0 0 15px; border: 0">
              <h3>Các bước phê duyệt tuần tự</h3>
              <button
                type="button"
                class="button secondary small"
                @click="
                  steps.push({ label: '', resolver: 'user', user_id: '' })
                "
              >
                <Plus :size="15" />Thêm bước
              </button>
            </div>
            <div
              v-for="(step, index) in steps"
              :key="index"
              class="step-editor"
            >
              <div class="builder-field-head">
                <span>BƯỚC {{ index + 1 }}</span
                ><button
                  type="button"
                  class="icon-button"
                  aria-label="Xóa bước"
                  @click="steps.splice(index, 1)"
                >
                  <Trash2 :size="15" />
                </button>
              </div>
              <div class="form-grid">
                <div class="field full-width">
                  <label :for="`step-label-${index}`">Tên bước</label
                  ><input
                    :id="`step-label-${index}`"
                    v-model="step.label"
                    required
                  />
                </div>
                <div class="field">
                  <label :for="`step-resolver-${index}`">Người duyệt</label
                  ><select
                    :id="`step-resolver-${index}`"
                    v-model="step.resolver"
                  >
                    <option value="department_manager">
                      Lãnh đạo phòng người gửi
                    </option>
                    <option value="user">Chỉ định thành viên</option>
                  </select>
                </div>
                <div v-if="step.resolver === 'user'" class="field">
                  <label :for="`step-user-${index}`">Thành viên nhận</label
                  ><select
                    :id="`step-user-${index}`"
                    v-model="step.user_id"
                    required
                  >
                    <option value="">Chọn người duyệt</option>
                    <option
                      v-for="user in users.data.value?.items"
                      :key="user.id"
                      :value="user.id"
                    >
                      {{ user.display_name }}
                    </option>
                  </select>
                </div>
              </div>
              <label class="checkbox-label"
                ><input
                  type="checkbox"
                  :checked="!!step.condition"
                  @change="
                    step.condition = ($event.target as HTMLInputElement).checked
                      ? {
                          field: fields[0]?.key || '',
                          operator: 'gte',
                          value: 0,
                        }
                      : undefined
                  "
                />Chỉ thực hiện bước này khi thỏa điều kiện</label
              >
              <div
                v-if="step.condition"
                class="form-grid"
                style="margin-top: 13px"
              >
                <div class="field">
                  <label
                    >Trường điều kiện<select
                      v-model="step.condition.field"
                      required
                    >
                      <option
                        v-for="field in fields"
                        :key="field.key"
                        :value="field.key"
                      >
                        {{ field.label || field.key }}
                      </option>
                    </select></label
                  >
                </div>
                <div class="field">
                  <label
                    >So sánh<select v-model="step.condition.operator">
                      <option value="eq">Bằng</option>
                      <option value="ne">Khác</option>
                      <option value="gt">Lớn hơn</option>
                      <option value="gte">Lớn hơn hoặc bằng</option>
                      <option value="lt">Nhỏ hơn</option>
                      <option value="lte">Nhỏ hơn hoặc bằng</option>
                    </select></label
                  >
                </div>
                <div class="field full-width">
                  <label
                    >Giá trị<input
                      v-model="step.condition.value"
                      :type="
                        fields.find(
                          (field) => field.key === step.condition?.field,
                        )?.type === 'number'
                          ? 'number'
                          : 'text'
                      "
                      required
                  /></label>
                </div>
              </div>
            </div>
          </div>
          <div class="notice warning">
            <ShieldCheck :size="19" /><span
              >Phát hành ngay sau khi kiểm tra hợp lệ. Người tạo không được tự
              duyệt; thiếu người nhận sẽ chặn trình hồ sơ.</span
            >
          </div></template
        >
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
            busy ? 'Đang lưu…' : modal === 'form' ? 'Phát hành mẫu' : 'Lưu'
          }}
        </button>
      </div>
    </form>
  </ModalDialog>
</template>
