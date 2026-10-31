<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { ref } from 'vue'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { RefreshCw, Sparkles } from 'lucide-vue-next'
import { formatDate } from '@dx/web-shared/api.ts'
import AssistantText from '../assistant/AssistantText.vue'
import { api } from '../api'
import { toast } from '../ui/toast'

/** "Today" in words at the top of the home page; written once a day and kept for the day. */
interface Digest {
  text: string
  created_at: string
}
const queryClient = useQueryClient()
const digest = useQuery({
  queryKey: ['ai-digest'],
  queryFn: () => api.request<{ digest: Digest | null }>('/ai/digest'),
})
const busy = ref(false)
async function write() {
  busy.value = true
  try {
    queryClient.setQueryData(['ai-digest'], await api.request<{ digest: Digest }>('/ai/digest', { method: 'POST' }))
  } catch (error) {
    toast.error(error)
  } finally {
    busy.value = false
  }
}
</script>
<template>
  <section class="ai-card" style="margin-bottom: 20px" aria-live="polite">
    <header>
      <span class="ai-title"><Sparkles :size="16" />Bản tin việc hôm nay</span>
      <button class="button secondary small ai-action" :disabled="busy" @click="write">
        <RefreshCw v-if="digest.data.value?.digest" :size="14" /><Sparkles v-else :size="14" />{{
          busy ? 'Đang viết…' : digest.data.value?.digest ? 'Cập nhật' : 'Tóm tắt ngày hôm nay'
        }}
      </button>
    </header>
    <AssistantText v-if="digest.data.value?.digest" :text="digest.data.value.digest.text" />
    <p v-else class="muted">Để AI điểm qua việc gấp, hồ sơ chờ duyệt và việc sắp quá hạn của bạn trong vài dòng.</p>
    <p v-if="digest.data.value?.digest" class="ai-note">
      Viết lúc {{ formatDate(digest.data.value.digest.created_at, true) }} từ danh sách việc bên dưới.
    </p>
  </section>
</template>
