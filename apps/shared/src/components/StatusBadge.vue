<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
defineProps<{ status: string }>()
const labels: Record<string, string> = {
  draft: 'Bản nháp',
  pending_workflow_start: 'Đang khởi tạo',
  submitted: 'Đã trình',
  processing: 'Đang xử lý',
  needs_revision: 'Cần chỉnh sửa',
  approved: 'Đã phê duyệt',
  rejected: 'Từ chối',
  withdrawn: 'Đã thu hồi',
  cancelled: 'Đã hủy',
  archived: 'Lưu trữ',
  pending: 'Chờ xử lý',
  waiting: 'Đang chờ',
  completed: 'Hoàn tất',
  queued: 'Trong hàng đợi',
  running: 'Đang chạy',
  succeeded: 'Thành công',
  failed: 'Thất bại',
  published: 'Đã phát hành',
  active: 'Đang hoạt động',
  closed: 'Đã đóng',
  error: 'Lỗi đồng bộ',
  clean: 'Sẵn sàng',
  returned: 'Trả lại',
  assigned: 'Đã giao',
  accepted: 'Đã tiếp nhận',
  in_progress: 'Đang thực hiện',
  blocked: 'Vướng mắc',
  not_matched: 'Không khớp điều kiện',
  skipped: 'Bỏ qua (chống lặp)',
  unknown: 'Chưa rõ kết quả',
  scheduled: 'Chưa hiệu lực',
  expired: 'Hết hạn',
  revoked: 'Đã thu hồi',
}
</script>
<template>
  <span class="status-badge" :class="`status-${status}`"
    ><span class="status-dot" />{{ labels[status] || status }}</span
  >
</template>
