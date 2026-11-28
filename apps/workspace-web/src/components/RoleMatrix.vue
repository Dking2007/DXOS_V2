<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { CircleAlert, LoaderCircle, Lock, RotateCcw, Save } from 'lucide-vue-next'
import type { Page } from '@dx/web-shared/api.ts'
import StatePanel from '@dx/web-shared/components/StatePanel.vue'
import { api } from '../api'
import { useSession } from '../stores/session'
import { PERMISSION_GROUPS, PERMISSIONS, roleLabel } from '../ui/labels'
import { toast } from '../ui/toast'
import { useUnsavedGuard } from '../ui/unsaved'
import { confirmDialog } from '@dx/web-shared/confirm.ts'

interface Role {
  key: string
  name: string
  permissions: string[]
  revision: number
}
const emit = defineEmits<{ dirty: [value: boolean] }>()
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
const copy = (items: Role[]) => Object.fromEntries(items.map((role) => [role.key, [...role.permissions]]))
const differs = (role: Role) =>
  [...(draft.value[role.key] ?? [])].sort().join() !== [...role.permissions].sort().join()
watch(
  () => roles.data.value,
  (data, before) => {
    if (!data) return
    // A background refetch must not wipe ticks the person has not saved yet.
    if (before && before.items.some(differs)) {
      for (const role of data.items) if (!(role.key in draft.value)) draft.value[role.key] = [...role.permissions]
      return
    }
    draft.value = copy(data.items)
  },
  { immediate: true },
)
function changed(role: Role) {
  return differs(role)
}
const dirty = computed(() => sorted.value.some(changed))
const changedCount = computed(() => sorted.value.filter(changed).length)
useUnsavedGuard(dirty)
watch(dirty, (value) => emit('dirty', value), { immediate: true })
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
  if (busy.value || !dirty.value) return
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
    // Take the saved state as the new baseline so the refetch replaces the draft.
    const saved = await api.request<Page<Role>>('/roles')
    draft.value = copy(saved.items)
    queryClient.setQueryData(['roles'], saved)
    await session.load()
  } catch (error) {
    toast.error(error)
    await queryClient.invalidateQueries({ queryKey: ['roles'] })
  } finally {
    busy.value = false
  }
}
async function reset() {
  if (!roles.data.value || !(await confirmDialog({ message: 'Bỏ mọi thay đổi phân quyền chưa lưu?', confirmLabel: 'Bỏ thay đổi', danger: true }))) return
  draft.value = copy(roles.data.value.items)
}
</script>
<template>
  <section class="card role-card">
    <header class="card-header">
      <div class="role-card-title">
        <span class="eyebrow">VAI TRÒ & QUYỀN</span>
        <h2>Mỗi vai trò được làm gì?</h2>
        <p class="muted">
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
    <div v-if="dirty" class="sticky-actions" role="region" aria-label="Thay đổi phân quyền chưa lưu">
      <span
        ><CircleAlert :size="18" aria-hidden="true" />Có thay đổi chưa lưu ở {{ changedCount }} vai trò.</span
      >
      <button class="button secondary" type="button" :disabled="busy" @click="reset">
        <RotateCcw :size="16" />Hoàn tác
      </button>
      <button class="button" type="button" :disabled="busy" :aria-busy="busy" @click="save">
        <LoaderCircle v-if="busy" :size="16" class="spin" aria-hidden="true" /><Save v-else :size="16" />{{
          busy ? 'Đang lưu…' : 'Lưu phân quyền'
        }}
      </button>
    </div>
  </section>
</template>
<style scoped>
/* overflow: clip (not hidden) keeps the card's rounded corners without breaking the sticky save bar. */
.role-card {
  overflow: clip;
}
.role-card-title {
  display: grid;
  gap: 4px;
}
.role-card-title .eyebrow {
  margin-bottom: 0;
}
.role-card-title p {
  font-size: 0.9375rem;
  line-height: 1.5;
}
.role-card .sticky-actions {
  gap: 12px;
  padding: 12px 16px 12px 20px;
}
</style>
