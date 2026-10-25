<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { Lock, RotateCcw, Save } from 'lucide-vue-next'
import type { Page } from '@dx/web-shared/api.ts'
import StatePanel from '@dx/web-shared/components/StatePanel.vue'
import { api } from '../api'
import { useSession } from '../stores/session'
import { PERMISSION_GROUPS, PERMISSIONS, roleLabel } from '../ui/labels'
import { toast } from '../ui/toast'
import { useUnsavedGuard } from '../ui/unsaved'

interface Role {
  key: string
  name: string
  permissions: string[]
  revision: number
}
const session = useSession()
const queryClient = useQueryClient()
const roles = useQuery({
  queryKey: ['roles'],
  queryFn: () => api.request<Page<Role>>('/roles'),
})
const ORDER = ['director', 'manager', 'staff', 'technical_admin']
const sorted = computed(() =>
  [...(roles.data.value?.items ?? [])].sort((a, b) => ORDER.indexOf(a.key) - ORDER.indexOf(b.key)),
)
// Working copy per role; compared with the server copy to show what changed.
const draft = ref<Record<string, string[]>>({})
watch(
  () => roles.data.value,
  (data) => {
    if (data) draft.value = Object.fromEntries(data.items.map((role) => [role.key, [...role.permissions]]))
  },
  { immediate: true },
)
function changed(role: Role) {
  const now = [...(draft.value[role.key] ?? [])].sort().join()
  return now !== [...role.permissions].sort().join()
}
const dirty = computed(() => sorted.value.some(changed))
useUnsavedGuard(dirty)
function has(role: string, permission: string) {
  return draft.value[role]?.includes(permission) ?? false
}
function locked(role: string, permission: string) {
  return role === session.user?.role && permission === 'organization.manage'
}
function toggle(role: string, permission: string) {
  if (locked(role, permission)) return
  const list = draft.value[role] ?? []
  draft.value[role] = has(role, permission) ? list.filter((item) => item !== permission) : [...list, permission]
}
const groups = computed(() =>
  PERMISSION_GROUPS.map((group) => ({
    group,
    items: Object.entries(PERMISSIONS)
      .filter(([, info]) => info.group === group)
      .map(([code, info]) => ({ code, ...info })),
  })),
)
const busy = ref(false)
async function save() {
  busy.value = true
  try {
    for (const role of sorted.value.filter(changed))
      await api.request(`/roles/${role.key}`, {
        method: 'PATCH',
        body: JSON.stringify({
          expected_revision: role.revision,
          name: role.name,
          permissions: draft.value[role.key],
        }),
      })
    toast.success('Đã lưu phân quyền. Người dùng thấy thay đổi ở lần tải trang kế tiếp.')
    await queryClient.invalidateQueries({ queryKey: ['roles'] })
    await session.load()
  } catch (error) {
    toast.error(error)
    await queryClient.invalidateQueries({ queryKey: ['roles'] })
  } finally {
    busy.value = false
  }
}
function reset() {
  if (roles.data.value)
    draft.value = Object.fromEntries(roles.data.value.items.map((role) => [role.key, [...role.permissions]]))
}
</script>
<template>
  <section class="card">
    <header class="card-header">
      <div>
        <span class="eyebrow">VAI TRÒ & QUYỀN</span>
        <h2>Mỗi vai trò được làm gì?</h2>
        <p class="muted" style="font-size: 14px; margin-top: 5px">
          Đánh dấu ô để cấp quyền cho cả vai trò. Quyền xem từng hồ sơ, tài liệu vẫn được kiểm tra riêng.
        </p>
      </div>
    </header>
    <StatePanel :loading="roles.isPending.value" :error="roles.error.value" @retry="roles.refetch()" />
    <div v-if="roles.data.value" class="matrix-scroll">
      <table class="role-matrix">
        <caption class="sr-only">
          Bảng phân quyền theo vai trò
        </caption>
        <thead>
          <tr>
            <th scope="col">Quyền</th>
            <th v-for="role in sorted" :key="role.key" scope="col" :class="{ changed: changed(role) }">
              {{ role.name || roleLabel(role.key) }}<small v-if="changed(role)">đã thay đổi</small>
            </th>
          </tr>
        </thead>
        <tbody v-for="group in groups" :key="group.group">
          <tr class="matrix-group">
            <th :colspan="sorted.length + 1" scope="colgroup">{{ group.group }}</th>
          </tr>
          <tr v-for="permission in group.items" :key="permission.code">
            <th scope="row">
              <strong>{{ permission.label }}</strong><small>{{ permission.hint }}</small>
            </th>
            <td v-for="role in sorted" :key="role.key">
              <label class="matrix-cell" :title="locked(role.key, permission.code) ? 'Không thể bỏ quyền này khỏi vai trò bạn đang dùng' : ''">
                <input
                  type="checkbox"
                  :checked="has(role.key, permission.code)"
                  :disabled="busy || locked(role.key, permission.code)"
                  :aria-label="`${permission.label} cho ${role.name}`"
                  @change="toggle(role.key, permission.code)"
                />
                <Lock v-if="locked(role.key, permission.code)" :size="13" aria-hidden="true" />
              </label>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-if="dirty" class="sticky-actions">
      <span>Có thay đổi phân quyền chưa lưu.</span>
      <button class="button secondary" type="button" :disabled="busy" @click="reset">
        <RotateCcw :size="15" />Hoàn tác
      </button>
      <button class="button" type="button" :disabled="busy" @click="save">
        <Save :size="16" />{{ busy ? 'Đang lưu…' : 'Lưu phân quyền' }}
      </button>
    </div>
  </section>
</template>
