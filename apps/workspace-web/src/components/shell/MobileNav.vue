<script setup lang="ts">
import { RouterLink } from 'vue-router'
import { ClipboardCheck, House, ListChecks, Menu, MessagesSquare } from 'lucide-vue-next'
import type { MeOverview } from '@dx/web-shared/types.ts'
import { badgeText } from '../../ui/nav'

defineProps<{ counts?: MeOverview['counts'] }>()
defineEmits<{ more: [] }>()
</script>
<template>
  <nav class="mobile-nav" aria-label="Điều hướng nhanh">
    <RouterLink to="/home"><House :size="21" /><span>Hôm nay</span></RouterLink>
    <RouterLink to="/tasks"
      ><ListChecks :size="21" /><span>Công việc</span
      ><i v-if="counts && counts.tasks + counts.tasks_to_review" class="nav-badge">{{
        badgeText(counts.tasks + counts.tasks_to_review)
      }}</i></RouterLink
    >
    <RouterLink to="/approvals"
      ><ClipboardCheck :size="21" /><span>Phê duyệt</span
      ><i v-if="counts?.approvals" class="nav-badge">{{ badgeText(counts.approvals) }}</i></RouterLink
    >
    <RouterLink to="/chat"
      ><MessagesSquare :size="21" /><span>Nhắn tin</span
      ><i v-if="counts?.chat" class="nav-badge">{{ badgeText(counts.chat) }}</i></RouterLink
    >
    <button type="button" aria-label="Mở toàn bộ menu" @click="$emit('more')">
      <Menu :size="21" /><span>Thêm</span>
    </button>
  </nav>
</template>
