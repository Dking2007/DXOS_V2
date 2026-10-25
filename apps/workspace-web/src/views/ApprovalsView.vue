<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import {
  ArrowRight,
  CheckCheck,
  ClipboardCheck,
  ChevronRight,
  UserRoundCheck,
} from 'lucide-vue-next'
import { api } from '../api'
import { toast } from '../ui/toast'
import { useSession } from '../stores/session'
import { errorText, formatDate, queryString } from '@dx/web-shared/api.ts'
import type { Page } from '@dx/web-shared/api.ts'
import type { ApprovalTask, User } from '@dx/web-shared/types.ts'
import StatePanel from '@dx/web-shared/components/StatePanel.vue'
import StatusBadge from '@dx/web-shared/components/StatusBadge.vue'
import ModalDialog from '@dx/web-shared/components/ModalDialog.vue'
const queryClient = useQueryClient()
const session = useSession()
interface Delegation {
  id: string
  delegator_id: string
  delegator_name: string
  delegate_name: string
  starts_at: string
  ends_at: string
  reason: string
  state: string
}
const delegations = useQuery({
  queryKey: ['delegations'],
  queryFn: () => api.request<Page<Delegation>>('/delegations'),
})
const users = useQuery({ queryKey: ['users'], queryFn: () => api.request<Page<User>>('/users') })
const showDelegate = ref(false)
const delegateId = ref('')
const startsAt = ref('')
const endsAt = ref('')
const delegateReason = ref('')
const delegationError = ref<unknown>(null)
async function createDelegation() {
  delegationError.value = null
  try {
    await api.request('/delegations', {
      method: 'POST',
      body: JSON.stringify({
        delegate_id: delegateId.value,
        starts_at: new Date(startsAt.value || Date.now()).toISOString(),
        ends_at: new Date(endsAt.value).toISOString(),
        reason: delegateReason.value,
      }),
    })
    showDelegate.value = false
    delegateReason.value = ''
    toast.success('Đã ủy quyền duyệt. Người nhận sẽ thấy hồ sơ trong hộp duyệt của họ.')
    await queryClient.invalidateQueries({ queryKey: ['delegations'] })
  } catch (cause) {
    delegationError.value = cause
  }
}
async function revoke(item: Delegation) {
  if (!window.confirm('Thu hồi ủy quyền này?')) return
  try {
    await api.request(`/delegations/${item.id}/revoke`, { method: 'POST' })
    toast.success('Đã thu hồi ủy quyền')
  } catch (cause) {
    toast.error(cause)
  }
  await queryClient.invalidateQueries({ queryKey: ['delegations'] })
}
const cursor = ref<string | null>(null)
const tasks = useQuery({
  queryKey: computed(() => ['approvals', cursor.value]),
  queryFn: () =>
    api.request<Page<ApprovalTask>>(
      `/approval-tasks${queryString({ cursor: cursor.value })}`,
    ),
  refetchInterval: 20_000,
})
</script>
<template>
  <header class="page-head">
    <div>
      <span class="eyebrow">HỘP VIỆC CỦA BẠN</span>
      <h1>Cần phê duyệt</h1>
      <p>Xem nội dung, đối chiếu tài liệu và ra quyết định có căn cứ.</p>
    </div>
    <div class="date-line">
      <CheckCheck :size="16" />Danh sách tự cập nhật mỗi 20 giây
    </div>
  </header>
  <section class="card">
    <header class="card-header">
      <h2>Hồ sơ được phân công</h2>
      <button
        class="button secondary small"
        :disabled="tasks.isFetching.value"
        @click="tasks.refetch()"
      >
        Làm mới
      </button>
    </header>
    <StatePanel
      :loading="tasks.isPending.value"
      :error="tasks.error.value"
      :empty="tasks.data.value?.items.length === 0"
      title="Bạn đã duyệt hết hồ sơ"
      description="Khi có hồ sơ cần bạn quyết định, nó sẽ hiện ở đây và trong mục Việc hôm nay. Sắp nghỉ phép? Bấm “Ủy quyền duyệt” để người khác duyệt thay."
      @retry="tasks.refetch()"
      ><RouterLink to="/cases" class="button small secondary">Xem tất cả hồ sơ</RouterLink></StatePanel
    >
    <div v-if="tasks.data.value?.items.length" class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Hồ sơ</th>
            <th>Bước xử lý</th>
            <th>Thời gian nhận</th>
            <th>Trạng thái</th>
            <th />
          </tr>
        </thead>
        <tbody>
          <tr v-for="task in tasks.data.value.items" :key="task.id">
            <td>
              <div class="primary-cell">
                <span class="file-icon"><ClipboardCheck :size="20" /></span>
                <div>
                  <RouterLink class="row-link" :to="`/cases/${task.case_id}`">{{
                    task.case_title || 'Hồ sơ cần phê duyệt'
                  }}</RouterLink
                  ><small class="mono">{{
                    task.case_code || 'Hồ sơ'
                  }}</small
                  ><small v-if="task.on_behalf_of" class="delegated-note"
                    ><UserRoundCheck :size="12" /> Duyệt thay {{ task.on_behalf_of }}</small
                  >
                </div>
              </div>
            </td>
            <td>{{ task.label || task.step_label || 'Phê duyệt' }}</td>
            <td class="muted">{{ formatDate(task.created_at, true) }}</td>
            <td>
              <StatusBadge :status="task.status || task.state || 'pending'" />
            </td>
            <td>
              <RouterLink
                :to="`/cases/${task.case_id}`"
                class="button secondary small"
                >Xem hồ sơ <ArrowRight :size="15"
              /></RouterLink>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-if="tasks.data.value?.has_more || cursor" class="pagination">
      <button
        class="button secondary small"
        :disabled="!cursor"
        @click="cursor = null"
      >
        Về đầu</button
      ><button
        class="button secondary small"
        :disabled="!tasks.data.value?.has_more"
        @click="cursor = tasks.data.value?.next_cursor ?? null"
      >
        Trang tiếp <ChevronRight :size="15" />
      </button>
    </div>
  </section>
  <section class="card" style="margin-top: 22px">
    <header class="card-header">
      <div>
        <span class="eyebrow">ỦY QUYỀN PHÊ DUYỆT</span>
        <h2>Khi bạn vắng mặt</h2>
      </div>
      <button class="button secondary small" @click="showDelegate = true">
        <UserRoundCheck :size="15" />Ủy quyền
      </button>
    </header>
    <p
      v-if="!delegations.data.value?.items.length"
      class="card-body muted"
      style="font-size: 14px"
    >
      Ủy quyền cho đồng nghiệp duyệt thay trong một khoảng thời gian. Người nhận chỉ xử lý
      hồ sơ được giao cho bạn, quyết định ghi rõ ai duyệt thay ai.
    </p>
    <div v-for="item in delegations.data.value?.items" :key="item.id" class="list-row">
      <div class="grow">
        <p>
          {{ item.delegator_name }} → {{ item.delegate_name }}
        </p>
        <small
          >{{ formatDate(item.starts_at, true) }} – {{ formatDate(item.ends_at, true) }} ·
          {{ item.reason }}</small
        >
      </div>
      <StatusBadge :status="item.state" />
      <button
        v-if="item.delegator_id === session.user?.id && ['active', 'scheduled'].includes(item.state)"
        class="button secondary small"
        @click="revoke(item)"
      >
        Thu hồi
      </button>
    </div>
  </section>
  <ModalDialog v-if="showDelegate" title="Ủy quyền phê duyệt" @close="showDelegate = false">
    <div v-if="delegationError" class="notice error error-inline">
      {{ errorText(delegationError) }}
    </div>
    <form class="stack" @submit.prevent="createDelegation">
      <div class="field">
        <label for="delegate">Người duyệt thay</label
        ><select id="delegate" v-model="delegateId" required>
          <option value="">Chọn đồng nghiệp</option>
          <option
            v-for="user in users.data.value?.items.filter((u) => u.id !== session.user?.id)"
            :key="user.id"
            :value="user.id"
          >
            {{ user.display_name }}
          </option>
        </select>
      </div>
      <div class="form-grid">
        <div class="field">
          <label for="delegate-start">Từ</label
          ><input id="delegate-start" v-model="startsAt" type="datetime-local" />
          <small>Để trống = ngay bây giờ.</small>
        </div>
        <div class="field">
          <label for="delegate-end">Đến<span class="required"> *</span></label
          ><input id="delegate-end" v-model="endsAt" type="datetime-local" required />
          <small>Tối đa 90 ngày.</small>
        </div>
      </div>
      <div class="field">
        <label for="delegate-reason">Lý do<span class="required"> *</span></label
        ><input id="delegate-reason" v-model="delegateReason" required maxlength="1000" />
      </div>
      <div class="form-actions">
        <button type="button" class="button secondary" @click="showDelegate = false">
          Hủy</button
        ><button class="button">Ủy quyền</button>
      </div>
    </form>
  </ModalDialog>
</template>
