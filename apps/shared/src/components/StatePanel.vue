<script setup lang="ts">
import { AlertCircle, Inbox, LoaderCircle } from 'lucide-vue-next'
import { ApiError, errorText } from '../api'
defineProps<{
  loading?: boolean
  error?: unknown
  empty?: boolean
  title?: string
  description?: string
}>()
defineEmits<{ retry: [] }>()
</script>
<template>
  <div v-if="loading" class="state-panel" role="status">
    <LoaderCircle class="spin" :size="25" /><strong>Đang tải dữ liệu…</strong
    ><span>Vui lòng chờ trong giây lát.</span>
  </div>
  <div v-else-if="error" class="state-panel state-error" role="alert">
    <AlertCircle :size="27" /><strong>{{ errorText(error) }}</strong
    ><code v-if="error instanceof ApiError && error.traceId"
      >Mã theo dõi: {{ error.traceId }}</code
    ><button class="button secondary" @click="$emit('retry')">Thử lại</button>
  </div>
  <div v-else-if="empty" class="state-panel">
    <Inbox :size="32" /><strong>{{ title || 'Chưa có dữ liệu' }}</strong
    ><span>{{
      description || 'Dữ liệu sẽ xuất hiện tại đây khi có thay đổi.'
    }}</span
    ><slot />
  </div>
</template>
