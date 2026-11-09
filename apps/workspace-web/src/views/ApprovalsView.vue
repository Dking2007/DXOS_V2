<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import StepAnswerDialog from '../components/StepAnswerDialog.vue'
import { computed, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import {
  ArrowRight,
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
  delegate_id: string
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
/** In force now or starting later: who acts for whom is what people need to see at a glance. */
const LIVE = ['active', 'scheduled']
const delegationGroups = computed(() => {
  const items = delegations.data.value?.items ?? []
  const me = session.user?.id
  return [
    {
      key: 'given',
      title: 'Bạn đang ủy quyền cho',
      empty: 'Bạn chưa ủy quyền cho ai. Hồ sơ giao cho bạn chỉ bạn xử lý.',
      items: items.filter((item) => item.delegator_id === me && LIVE.includes(item.state)),
    },
    {
      key: 'received',
      title: 'Bạn đang được ủy quyền',
      empty: 'Không ai đang nhờ bạn duyệt thay.',
      items: items.filter((item) => item.delegate_id === me && LIVE.includes(item.state)),
    },
  ]
})
const pastDelegations = computed(() =>
  (delegations.data.value?.items ?? []).filter((item) => !LIVE.includes(item.state)),
)
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
/** The deadline the process set for this step has passed. */
function stepLate(task: { due_at?: string | null; state?: string; status?: string }) {
  return !!task.due_at && new Date(task.due_at).getTime() < Date.now() && (task.state || task.status) === 'pending'
}
const answering = ref<ApprovalTask | null>(null)
async function answered() {
  answering.value = null
  await tasks.refetch()
}
</script>
<template>
  <StepAnswerDialog v-if="answering" :task="answering" mode="answer" @close="answering = null" @done="answered" />
  <header class="page-head compact">
    <h1 class="sr-only">Cần phê duyệt</h1>
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
            <th>Hạn xử lý</th>
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
                  <RouterLink v-if="task.case_id" class="row-link" :to="`/cases/${task.case_id}`">{{
                    task.case_title || 'Hồ sơ cần phê duyệt'
                  }}</RouterLink>
                  <RouterLink v-else-if="task.subject?.link" class="row-link" :to="task.subject.link">{{ task.case_title }}</RouterLink>
                  <span v-else>{{ task.case_title }}</span>
                  <small v-if="!task.case_id || task.case_number" class="mono">{{
                    task.case_id
                      ? `HS-${String(task.case_number).padStart(6, '0')}`
                      : task.subject?.type === 'post'
                        ? 'Bài viết'
                        : 'Công việc'
                  }}</small
                  ><small v-if="task.on_behalf_of" class="delegated-note"
                    ><UserRoundCheck :size="12" /> Duyệt thay {{ task.on_behalf_of }}</small
                  >
                </div>
              </div>
            </td>
            <td>{{ task.label || task.step_label || 'Phê duyệt' }}</td>
            <td class="muted">{{ formatDate(task.created_at, true) }}</td>
            <td :class="{ 'overdue-text': stepLate(task) }">
              {{ task.due_at ? formatDate(task.due_at, true) : '—' }}<template v-if="stepLate(task)"> · quá hạn</template>
            </td>
            <td>
              <StatusBadge :status="task.status || task.state || 'pending'" />
            </td>
            <td>
              <RouterLink
                v-if="task.case_id"
                :to="`/cases/${task.case_id}`"
                class="button secondary small"
                >Xem hồ sơ <ArrowRight :size="15"
              /></RouterLink>
              <button v-else class="button secondary small" @click="answering = task">Xử lý</button>
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
        <h2>Ủy quyền phê duyệt</h2>
        <small class="muted">Nhờ đồng nghiệp duyệt thay khi bạn vắng mặt.</small>
      </div>
      <button class="button secondary small" @click="showDelegate = true">
        <UserRoundCheck :size="15" />Ủy quyền
      </button>
    </header>
    <div class="card-body delegation-groups">
      <div v-for="group in delegationGroups" :key="group.key" class="delegation-group">
        <span class="section-label">{{ group.title }}</span>
        <p v-if="!group.items.length" class="muted">{{ group.empty }}</p>
        <div v-for="item in group.items" :key="item.id" class="list-row">
          <div class="grow">
            <p>
              <strong>{{ group.key === 'given' ? item.delegate_name : item.delegator_name }}</strong>
              <template v-if="group.key === 'given'"> duyệt thay bạn</template
              ><template v-else> nhờ bạn duyệt thay</template>
            </p>
            <small
              >{{ item.state === 'scheduled' ? 'Bắt đầu' : 'Từ' }} {{ formatDate(item.starts_at, true) }} đến
              {{ formatDate(item.ends_at, true) }}<template v-if="item.reason"> · {{ item.reason }}</template></small
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
      </div>
      <details v-if="pastDelegations.length" class="delegation-past">
        <summary>Đã hết hạn hoặc đã thu hồi ({{ pastDelegations.length }})</summary>
        <div v-for="item in pastDelegations" :key="item.id" class="list-row">
          <div class="grow">
            <p>{{ item.delegator_name }} → {{ item.delegate_name }}</p>
            <small
              >{{ formatDate(item.starts_at, true) }} – {{ formatDate(item.ends_at, true) }}<template v-if="item.reason">
                · {{ item.reason }}</template
              ></small
            >
          </div>
          <StatusBadge :status="item.state" />
        </div>
      </details>
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
