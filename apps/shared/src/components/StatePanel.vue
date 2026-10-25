<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { AlertCircle, Inbox } from 'lucide-vue-next'
import { ApiError, errorText } from '../api'
withDefaults(
  defineProps<{
    loading?: boolean
    // eslint-disable-next-line vue/require-default-prop -- any thrown value; absent means no error
    error?: unknown
    empty?: boolean
    title?: string
    description?: string
    compact?: boolean
    rows?: number
  }>(),
  { rows: 3, title: '', description: '' },
)
defineEmits<{ retry: [] }>()
</script>
<template>
  <div v-if="loading" class="skeleton-list" :class="{ compact }" role="status" aria-live="polite">
    <span class="sr-only">Đang tải dữ liệu…</span>
    <div v-for="row in rows" :key="row" class="skeleton-row" aria-hidden="true">
      <span class="skeleton skeleton-avatar" />
      <span class="skeleton-lines"
        ><span class="skeleton" :style="{ width: `${78 - ((row * 13) % 30)}%` }" /><span
          class="skeleton short"
      /></span>
    </div>
  </div>
  <div v-else-if="error" class="state-panel state-error" :class="{ compact }" role="alert">
    <AlertCircle :size="27" aria-hidden="true" /><strong>{{ errorText(error) }}</strong
    ><code v-if="error instanceof ApiError && error.traceId"
      >Mã theo dõi: {{ error.traceId }}</code
    ><button class="button secondary" type="button" @click="$emit('retry')">Thử lại</button>
  </div>
  <div v-else-if="empty" class="state-panel" :class="{ compact }">
    <span class="state-illustration" aria-hidden="true"><Inbox :size="28" /></span
    ><strong>{{ title || 'Chưa có dữ liệu' }}</strong
    ><span>{{
      description || 'Dữ liệu sẽ xuất hiện tại đây khi có thay đổi.'
    }}</span
    ><slot />
  </div>
</template>
