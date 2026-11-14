<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<!-- The assistant's "Trợ lý công việc" tab: questions about the dossier on screen. The AI reads this
     dossier only (form, process, tasks, attachments) and says what it answered from. The conversation
     stays in this browser tab, one per dossier. -->
<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useQueryClient } from '@tanstack/vue-query'
import { FileText, SendHorizontal } from 'lucide-vue-next'
import { errorText } from '@dx/web-shared/api.ts'
import { api } from '../api'
import { useAi } from '../ai/useAi'
import AssistantText from './AssistantText.vue'
import { pendingCaseQuestion } from './state'

const props = defineProps<{ caseId: string; suggestions: string[] }>()
interface Turn {
  role: 'user' | 'assistant'
  content: string
  sources?: string[]
}
const storageKey = computed(() => `case-ask:${props.caseId}`)
function restore(): Turn[] {
  try {
    return JSON.parse(sessionStorage.getItem(storageKey.value) ?? '[]') as Turn[]
  } catch {
    return []
  }
}
const turns = ref<Turn[]>(restore())
const draft = ref('')
const busy = ref(false)
const error = ref('')
const scroller = ref<HTMLElement | null>(null)
const input = ref<HTMLTextAreaElement | null>(null)
const { status } = useAi()
const queryClient = useQueryClient()

watch(
  turns,
  (value) => {
    try {
      sessionStorage.setItem(storageKey.value, JSON.stringify(value.slice(-20)))
    } catch {
      // Private windows may refuse storage; the conversation simply is not kept.
    }
  },
  { deep: true },
)
async function scrollDown() {
  await nextTick()
  scroller.value?.scrollTo({ top: scroller.value.scrollHeight })
}
async function send(text = draft.value) {
  const question = text.trim()
  if (question.length < 2 || busy.value) return
  error.value = ''
  const history = turns.value.slice(-8).map(({ role, content }) => ({ role, content }))
  turns.value.push({ role: 'user', content: question })
  draft.value = ''
  busy.value = true
  void scrollDown()
  try {
    const answer = await api.request<{ answer: string; sources: string[] }>(`/ai/cases/${props.caseId}/ask`, {
      method: 'POST',
      body: JSON.stringify({ question, history }),
    })
    turns.value.push({ role: 'assistant', content: answer.answer, sources: answer.sources })
    // The daily allowance just went down by one.
    void queryClient.invalidateQueries({ queryKey: ['ai-features'] })
  } catch (cause) {
    error.value = errorText(cause)
    draft.value = question
    turns.value.pop()
  } finally {
    busy.value = false
    await scrollDown()
    input.value?.focus()
  }
}
function onKey(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault()
    void send()
  }
}
function clear() {
  turns.value = []
  error.value = ''
  input.value?.focus()
}
// A question picked on the dossier page arrives here once the tab is showing.
watch(
  pendingCaseQuestion,
  (question) => {
    if (!question) return
    pendingCaseQuestion.value = ''
    void send(question)
  },
  { immediate: true },
)
onMounted(() => {
  void scrollDown()
  input.value?.focus()
})
defineExpose({ clear, turns })
</script>

<template>
  <div ref="scroller" class="assistant-body" aria-live="polite">
    <div class="assistant-msg bot">
      Tôi đã đọc hồ sơ này: nội dung biểu mẫu, tài liệu đính kèm, quy trình đã đi qua và ý kiến của từng bước. Bạn
      muốn hỏi gì?
    </div>
    <div v-if="!turns.length && suggestions.length" class="assistant-suggestions">
      <button v-for="item in suggestions" :key="item" type="button" :disabled="busy" @click="send(item)">
        {{ item }}
      </button>
    </div>
    <template v-for="(turn, index) in turns" :key="index">
      <div v-if="turn.role === 'user'" class="assistant-msg me">{{ turn.content }}</div>
      <div v-else class="assistant-msg bot">
        <AssistantText :text="turn.content" />
        <div v-if="turn.sources?.length" class="assistant-sources">
          <FileText :size="13" />
          <span v-for="source in turn.sources" :key="source" :title="source">{{ source }}</span>
        </div>
      </div>
    </template>
    <div v-if="busy" class="assistant-msg bot typing" role="status" aria-label="AI đang đọc hồ sơ">
      <i /><i /><i />
    </div>
    <p v-if="error" class="assistant-error" role="alert">{{ error }}</p>
  </div>
  <form class="assistant-input" @submit.prevent="send()">
    <textarea
      ref="input"
      v-model="draft"
      rows="1"
      maxlength="1000"
      placeholder="Hỏi về hồ sơ này… (Enter để gửi)"
      aria-label="Câu hỏi về hồ sơ"
      @keydown="onKey"
    />
    <button class="assistant-send" type="submit" :disabled="busy || draft.trim().length < 2" aria-label="Gửi câu hỏi">
      <SendHorizontal :size="18" />
    </button>
  </form>
  <footer class="assistant-foot">
    <span>AI chỉ đọc hồ sơ này và có thể nhầm.</span>
    <span v-if="status.data.value?.remaining != null">Còn {{ status.data.value.remaining }} lượt</span>
  </footer>
</template>
