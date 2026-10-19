<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { useQuery } from '@tanstack/vue-query'
import {
  ArrowRight,
  CheckCheck,
  ClipboardCheck,
  ChevronRight,
} from 'lucide-vue-next'
import { api } from '../api'
import { formatDate, queryString } from '@dx/web-shared/api.ts'
import type { Page } from '@dx/web-shared/api.ts'
import type { ApprovalTask } from '@dx/web-shared/types.ts'
import StatePanel from '@dx/web-shared/components/StatePanel.vue'
import StatusBadge from '@dx/web-shared/components/StatusBadge.vue'
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
      title="Không có hồ sơ đang chờ"
      description="Mọi hồ sơ cần bạn phê duyệt sẽ được tập trung tại đây. Bạn không cần kiểm tra từng phòng ban."
      @retry="tasks.refetch()"
    />
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
                    task.case_code || task.case_id.slice(0, 12)
                  }}</small>
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
</template>
