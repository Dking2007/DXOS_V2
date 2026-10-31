<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { ref, watch } from 'vue'
import { Sparkles } from 'lucide-vue-next'
import { formatDate } from '@dx/web-shared/api.ts'
import AssistantText from '../assistant/AssistantText.vue'
import { api } from '../api'
import { toast } from '../ui/toast'

/** The report page read out in words, for the same period and scope as the figures beside it. */
const props = defineProps<{ days: number; scope: string }>()
const result = ref<{ text: string; created_at: string } | null>(null)
const busy = ref(false)
watch(
  () => [props.days, props.scope],
  () => (result.value = null),
)
async function write() {
  busy.value = true
  try {
    result.value = await api.request('/ai/reports/narrative', {
      method: 'POST',
      body: JSON.stringify({ days: props.days, scope: props.scope }),
    })
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
      <span class="ai-title"><Sparkles :size="16" />Nhận xét điều hành</span>
      <button class="button secondary small ai-action" :disabled="busy" @click="write">
        <Sparkles :size="14" />{{ busy ? 'Đang viết…' : result ? 'Viết lại' : 'Viết nhận xét bằng AI' }}
      </button>
    </header>
    <AssistantText v-if="result" :text="result.text" />
    <p v-else class="muted">AI đọc các số liệu trên trang này, nêu tình hình, chỗ đang chậm và gợi ý xử lý.</p>
    <p v-if="result" class="ai-note">
      Viết lúc {{ formatDate(result.created_at, true) }} từ số liệu bạn được xem; kiểm tra lại trước khi dùng trong báo cáo.
    </p>
  </section>
</template>
