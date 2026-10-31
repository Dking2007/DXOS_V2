<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { MessageSquareText, Send, Sparkles } from 'lucide-vue-next'
import ModalDialog from '@dx/web-shared/components/ModalDialog.vue'
import { errorText } from '@dx/web-shared/api.ts'
import { api } from '../api'

/** Summary of a document and questions about it; every answer points at the page it rests on. */
const props = defineProps<{ file: { id: string; name: string } }>()
defineEmits<{ close: [] }>()
interface Summary {
  points: { text: string; page: number | null }[]
  kind: string
  unit: string
}
interface Answer {
  question: string
  answer: string
  citations: { page: number; quote: string; verified: boolean }[]
  unit: string
}
const summary = ref<Summary | null>(null)
const summaryError = ref('')
const loading = ref(true)
const question = ref('')
const asking = ref(false)
const answers = ref<Answer[]>([])
const askError = ref('')

onMounted(async () => {
  try {
    summary.value = await api.request<Summary>(`/ai/files/${props.file.id}/summary`, { method: 'POST' })
  } catch (error) {
    summaryError.value = errorText(error)
  } finally {
    loading.value = false
  }
})
async function ask() {
  const text = question.value.trim()
  if (!text) return
  asking.value = true
  askError.value = ''
  try {
    const result = await api.request<Omit<Answer, 'question'>>(`/ai/files/${props.file.id}/ask`, {
      method: 'POST',
      body: JSON.stringify({ question: text }),
    })
    answers.value.unshift({ question: text, ...result })
    question.value = ''
  } catch (error) {
    askError.value = errorText(error)
  } finally {
    asking.value = false
  }
}
</script>
<template>
  <ModalDialog :title="`AI đọc “${file.name}”`" wide @close="$emit('close')">
    <div class="stack">
      <section class="ai-card" aria-live="polite">
        <header><span class="ai-title"><Sparkles :size="16" />Tóm tắt{{ summary?.kind ? ` · ${summary.kind}` : '' }}</span></header>
        <p v-if="loading" class="muted">AI đang đọc tài liệu…</p>
        <p v-else-if="summaryError" class="muted">{{ summaryError }}</p>
        <ul v-else-if="summary">
          <li v-for="(point, index) in summary.points" :key="index">
            {{ point.text }}<small v-if="point.page" class="muted"> ({{ summary.unit }} {{ point.page }})</small>
          </li>
        </ul>
      </section>
      <form class="inline-actions" @submit.prevent="ask">
        <label class="sr-only" for="doc-question">Câu hỏi về tài liệu</label>
        <input
          id="doc-question"
          v-model="question"
          class="grow"
          maxlength="1000"
          placeholder="Hỏi về tài liệu này, ví dụ: Thời hạn bảo hành bao lâu?"
          :disabled="asking"
        />
        <button class="button ai-action" :disabled="asking || question.trim().length < 2">
          <Send :size="15" />{{ asking ? 'Đang tìm…' : 'Hỏi' }}
        </button>
      </form>
      <div v-if="askError" class="notice error">{{ askError }}</div>
      <section v-for="(item, index) in answers" :key="index" class="ai-card">
        <header><span class="ai-title"><MessageSquareText :size="16" />{{ item.question }}</span></header>
        <p>{{ item.answer }}</p>
        <span
          v-for="(citation, n) in item.citations"
          :key="n"
          class="ai-citation"
          :class="{ unverified: !citation.verified }"
          >{{ item.unit }} {{ citation.page }}: “{{ citation.quote }}”<template v-if="!citation.verified">
            · không tìm thấy nguyên văn câu này, hãy kiểm tra lại</template
          ></span
        >
      </section>
      <p class="ai-note">Câu trả lời do AI tạo, chỉ dựa trên nội dung tài liệu. Đối chiếu trang được trích trước khi dùng.</p>
    </div>
  </ModalDialog>
</template>
