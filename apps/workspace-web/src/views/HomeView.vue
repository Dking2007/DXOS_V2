<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { useQuery } from '@tanstack/vue-query'
import {
  ArrowRight,
  CalendarDays,
  ClipboardCheck,
  FilePlus2,
  FolderClosed,
  History,
  ShieldCheck,
} from 'lucide-vue-next'
import { api } from '../api'
import { useSession } from '../stores/session'
import type { Page } from '@dx/web-shared/api.ts'
import { formatDate } from '@dx/web-shared/api.ts'
import type { ApprovalTask, CaseItem } from '@dx/web-shared/types.ts'
import StatePanel from '@dx/web-shared/components/StatePanel.vue'
import StatusBadge from '@dx/web-shared/components/StatusBadge.vue'
const session = useSession()
const today = new Intl.DateTimeFormat('vi-VN', {
  weekday: 'long',
  day: 'numeric',
  month: 'long',
  year: 'numeric',
}).format(new Date())
const firstName = computed(
  () => session.user?.display_name.split(' ').slice(-1)[0] ?? '',
)
const approvals = useQuery({
  queryKey: ['approvals', 'home'],
  queryFn: () => api.request<Page<ApprovalTask>>('/approval-tasks'),
})
const cases = useQuery({
  queryKey: ['cases', 'home'],
  queryFn: () => api.request<Page<CaseItem>>('/cases?limit=6'),
})
</script>
<template>
  <section class="welcome-section">
    <div>
      <span class="eyebrow">KHÔNG GIAN CỦA BẠN</span>
      <h1>Chào {{ firstName }}, bắt đầu công việc.</h1>
      <p>Những hồ sơ cần bạn xử lý, cùng tài liệu và hoạt động mới nhất.</p>
    </div>
    <div class="date-block">
      <CalendarDays
        :size="18"
        style="display: inline; vertical-align: middle; margin-right: 7px"
      />{{ today }}
    </div>
  </section>
  <div class="home-columns">
    <div class="stack">
      <section class="card">
        <header class="card-header">
          <div>
            <span class="eyebrow">ƯU TIÊN XỬ LÝ</span>
            <h2>Hồ sơ cần quyết định</h2>
          </div>
          <RouterLink to="/approvals" class="button ghost small"
            >Xem hộp duyệt <ArrowRight :size="15"
          /></RouterLink>
        </header>
        <StatePanel
          :loading="approvals.isPending.value"
          :error="approvals.error.value"
          :empty="approvals.data.value?.items.length === 0"
          title="Chưa có hồ sơ chờ bạn duyệt"
          description="Khi được phân công, hồ sơ sẽ xuất hiện tại đây cùng bước cần xử lý."
          @retry="approvals.refetch()"
        /><RouterLink
          v-for="task in approvals.data.value?.items.slice(0, 5)"
          :key="task.id"
          :to="`/cases/${task.case_id}`"
          class="list-row"
          style="color: inherit; text-decoration: none"
          ><span class="file-icon"><ClipboardCheck :size="19" /></span>
          <div class="grow">
            <p>{{ task.case_title || task.case_code || 'Hồ sơ cần xử lý' }}</p>
            <small
              >{{ task.label || task.step_label || 'Phê duyệt hồ sơ' }} ·
              {{ formatDate(task.created_at) }}</small
            >
          </div>
          <ArrowRight :size="17" class="muted"
        /></RouterLink>
      </section>
      <section class="card">
        <header class="card-header">
          <div>
            <span class="eyebrow">THEO DÕI TIẾN TRÌNH</span>
            <h2>Hồ sơ gần đây</h2>
          </div>
          <RouterLink to="/cases" class="button ghost small"
            >Tất cả hồ sơ <ArrowRight :size="15"
          /></RouterLink>
        </header>
        <StatePanel
          :loading="cases.isPending.value"
          :error="cases.error.value"
          :empty="cases.data.value?.items.length === 0"
          title="Hồ sơ đầu tiên bắt đầu từ bạn"
          description="Tạo hồ sơ từ mẫu có sẵn, đính kèm tài liệu và chuyển đến người duyệt phù hợp."
          @retry="cases.refetch()"
          ><RouterLink to="/cases?create=1" class="button small"
            >Tạo hồ sơ</RouterLink
          ></StatePanel
        >
        <div
          v-for="item in cases.data.value?.items.slice(0, 6)"
          :key="item.id"
          class="list-row"
        >
          <div class="grow">
            <RouterLink :to="`/cases/${item.id}`" class="row-link">{{
              item.title
            }}</RouterLink
            ><small
              ><span class="mono">{{ item.code }}</span> ·
              {{ formatDate(item.updated_at || item.created_at) }}</small
            >
          </div>
          <StatusBadge :status="item.status" />
        </div>
      </section>
    </div>
    <aside class="stack" style="align-content: start">
      <section class="card">
        <header class="card-header"><h2>Bắt đầu từ đây</h2></header>
        <RouterLink to="/cases?create=1" class="home-launcher"
          ><span><FilePlus2 :size="21" /></span>
          <div>
            <strong>Tạo một hồ sơ</strong
            ><small>Chọn mẫu, điền thông tin, chuyển duyệt</small>
          </div>
          <ArrowRight :size="17" /></RouterLink
        ><RouterLink to="/drive" class="home-launcher"
          ><span><FolderClosed :size="21" /></span>
          <div>
            <strong>Mở kho tài liệu</strong
            ><small>Tải lên, chia sẻ và quản lý phiên bản</small>
          </div>
          <ArrowRight :size="17" /></RouterLink
        ><RouterLink to="/approvals" class="home-launcher"
          ><span><ClipboardCheck :size="21" /></span>
          <div>
            <strong>Xem hộp phê duyệt</strong
            ><small>Kiểm tra và ra quyết định</small>
          </div>
          <ArrowRight :size="17"
        /></RouterLink>
      </section>
      <section class="card">
        <div class="card-body">
          <ShieldCheck
            :size="27"
            style="color: var(--teal); margin-bottom: 15px"
          />
          <h3>Mỗi quyết định có căn cứ</h3>
          <p
            class="muted"
            style="font-size: 14px; line-height: 1.7; margin-top: 10px"
          >
            Hồ sơ khi trình duyệt giữ nguyên bản thông tin và phiên bản tài
            liệu. Chỉnh sửa về sau không làm thay đổi nội dung đã trình.
          </p>
          <div class="date-line" style="margin-top: 20px">
            <History :size="15" /> Lịch sử được giữ theo từng lần trình
          </div>
        </div>
      </section>
    </aside>
  </div>
  <div class="intro-strip">
    <ShieldCheck :size="24" />
    <p>
      <strong>Quyền truy cập đi cùng dữ liệu.</strong> Bạn chỉ nhìn thấy hồ sơ,
      tài liệu và nhiệm vụ được cấp quyền. Các danh sách được lấy trực tiếp từ
      hệ thống.
    </p>
  </div>
</template>
