<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ListPlus, Sparkles } from 'lucide-vue-next'
import ModalDialog from '@dx/web-shared/components/ModalDialog.vue'
import { errorText } from '@dx/web-shared/api.ts'
import { api } from '../api'

/** A long conversation in a few lines, what was agreed, and work to hand out from it. */
const props = defineProps<{ conversationId: string; title: string }>()
const emit = defineEmits<{ close: []; task: [sentence: string] }>()
interface Summary {
  summary: string[]
  decisions: string[]
  actions: { text: string; assignee: string | null }[]
  messages: number
}
const result = ref<Summary | null>(null)
const error = ref('')
onMounted(async () => {
  try {
    result.value = await api.request<Summary>(`/ai/conversations/${props.conversationId}/summary`, {
      method: 'POST',
      body: JSON.stringify({}),
    })
  } catch (cause) {
    error.value = errorText(cause)
  }
})
</script>
<template>
  <ModalDialog :title="`Tóm tắt: ${title}`" @close="emit('close')">
    <div class="stack" aria-live="polite">
      <p v-if="!result && !error" class="muted">AI đang đọc cuộc trò chuyện…</p>
      <div v-if="error" class="notice error">{{ error }}</div>
      <template v-if="result">
        <section class="ai-card">
          <header><span class="ai-title"><Sparkles :size="16" />Nội dung chính</span></header>
          <ul><li v-for="(line, index) in result.summary" :key="index">{{ line }}</li></ul>
        </section>
        <section v-if="result.decisions.length" class="ai-card">
          <header><span class="ai-title">Đã thống nhất</span></header>
          <ul><li v-for="(line, index) in result.decisions" :key="index">{{ line }}</li></ul>
        </section>
        <section v-if="result.actions.length" class="ai-card">
          <header><span class="ai-title">Việc cần làm</span></header>
          <div v-for="(action, index) in result.actions" :key="index" class="ai-issue">
            <span class="grow">{{ action.text }}</span>
            <button class="button secondary small ai-action" @click="emit('task', action.text)">
              <ListPlus :size="14" />Tạo việc
            </button>
          </div>
        </section>
        <p class="ai-note">Tóm tắt {{ result.messages }} tin nhắn gần nhất bạn xem được. Do AI viết, hãy đọc lại tin gốc khi cần.</p>
      </template>
    </div>
  </ModalDialog>
</template>
