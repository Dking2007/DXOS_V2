<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useQueryClient } from '@tanstack/vue-query'
import { FileText, RotateCcw, Send, Sparkles, X } from 'lucide-vue-next'
import { errorText } from '@dx/web-shared/api.ts'
import { api } from '../api'
import AssistantText from '../assistant/AssistantText.vue'
import '../assistant/assistant.css'
import { useAi } from './useAi'

/**
 * Questions about the dossier on screen. The AI reads this dossier only (form, process, tasks,
 * attachments) and says which part it answered from. The conversation stays in this browser tab.
 */
const props = defineProps<{
  caseId: string
  caseTitle: string
  /** A question typed or picked on the dossier page, asked as soon as the drawer opens. */
  initialQuestion?: string
  /** Suggested questions that fit the dossier's state; a general set otherwise. */
  suggestions?: string[]
}>()
const emit = defineEmits<{ close: [] }>()
interface Turn {
  role: 'user' | 'assistant'
  content: string
  sources?: string[]
}
const GENERAL = [
  'Hồ sơ này đề nghị gì, giá trị bao nhiêu?',
  'Hồ sơ đang chờ ai xử lý, hạn khi nào?',
  'Các bước trước đã có ý kiến gì?',
  'Tài liệu đính kèm có khớp với nội dung biểu mẫu không?',
]
const SUGGESTIONS = props.suggestions?.length ? props.suggestions : GENERAL
const storageKey = `case-ask:${props.caseId}`
function restore(): Turn[] {
  try {
    return JSON.parse(sessionStorage.getItem(storageKey) ?? '[]') as Turn[]
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
      sessionStorage.setItem(storageKey, JSON.stringify(value.slice(-20)))
    } catch {
      // Private windows may refuse storage; the conversation simply is not kept.
    }
  },
  { deep: true },
)
function scrollDown() {
  void nextTick(() => scroller.value?.scrollTo({ top: scroller.value.scrollHeight, behavior: 'smooth' }))
}
async function send(text = draft.value) {
  const question = text.trim()
  if (question.length < 2 || busy.value) return
  error.value = ''
  const history = turns.value.slice(-8).map(({ role, content }) => ({ role, content }))
  turns.value.push({ role: 'user', content: question })
  draft.value = ''
  busy.value = true
  scrollDown()
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
    scrollDown()
    void nextTick(() => input.value?.focus())
  }
}
function onEnter(event: KeyboardEvent) {
  if (event.shiftKey || event.isComposing) return
  event.preventDefault()
  void send()
}
function clear() {
  turns.value = []
  error.value = ''
  input.value?.focus()
}
function onKey(event: KeyboardEvent) {
  if (event.key === 'Escape') emit('close')
}
onMounted(() => {
  window.addEventListener('keydown', onKey)
  scrollDown()
  input.value?.focus()
  if (props.initialQuestion?.trim()) void send(props.initialQuestion)
})
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
</script>
<template>
  <div class="ask-backdrop" @click="emit('close')" />
  <section class="ask-drawer" role="dialog" aria-modal="false" aria-label="Hỏi AI về hồ sơ">
    <header class="ask-head">
      <span class="ask-avatar" aria-hidden="true"><Sparkles :size="19" /></span>
      <div class="grow">
        <strong>Hỏi AI về hồ sơ</strong>
        <small :title="caseTitle">{{ caseTitle }}</small>
      </div>
      <button
        v-if="turns.length"
        class="icon-button"
        type="button"
        title="Bắt đầu cuộc hỏi mới"
        aria-label="Bắt đầu cuộc hỏi mới"
        @click="clear"
      >
        <RotateCcw :size="16" />
      </button>
      <button class="icon-button" type="button" aria-label="Đóng" title="Đóng (Esc)" @click="emit('close')">
        <X :size="17" />
      </button>
    </header>
    <div ref="scroller" class="ask-body" aria-live="polite">
      <div class="assistant-msg bot">
        Tôi đã đọc hồ sơ này: nội dung biểu mẫu, tài liệu đính kèm, quy trình đã đi qua và ý kiến của từng bước. Bạn
        muốn hỏi gì?
      </div>
      <div v-if="!turns.length" class="ask-suggestions">
        <button v-for="item in SUGGESTIONS" :key="item" type="button" :disabled="busy" @click="send(item)">
          {{ item }}
        </button>
      </div>
      <template v-for="(turn, index) in turns" :key="index">
        <div v-if="turn.role === 'user'" class="assistant-msg me">{{ turn.content }}</div>
        <div v-else class="assistant-msg bot">
          <AssistantText :text="turn.content" />
          <div v-if="turn.sources?.length" class="ask-sources">
            <span>Dựa trên:</span>
            <span v-for="source in turn.sources" :key="source" class="ask-source"
              ><FileText :size="12" />{{ source }}</span
            >
          </div>
        </div>
      </template>
      <div v-if="busy" class="assistant-msg bot typing" role="status" aria-label="AI đang đọc hồ sơ">
        <i /><i /><i />
      </div>
      <p v-if="error" class="assistant-error" role="alert">{{ error }}</p>
    </div>
    <form class="ask-input" @submit.prevent="send()">
      <textarea
        ref="input"
        v-model="draft"
        rows="2"
        maxlength="1000"
        placeholder="Hỏi về hồ sơ này… (Enter để gửi, Shift+Enter xuống dòng)"
        aria-label="Câu hỏi về hồ sơ"
        :disabled="busy"
        @keydown.enter="onEnter"
      />
      <button class="ask-send" type="submit" :disabled="busy || draft.trim().length < 2" aria-label="Gửi câu hỏi">
        <Send :size="17" />
      </button>
    </form>
    <footer class="ask-foot">
      AI chỉ đọc hồ sơ này và có thể nhầm; đối chiếu trước khi quyết định. Cuộc hỏi đáp chỉ lưu trong tab trình duyệt
      này<template v-if="status.data.value?.remaining != null">
        · còn {{ status.data.value.remaining }} lượt hôm nay</template
      >.
    </footer>
  </section>
</template>
<style scoped>
.ask-backdrop {
  position: fixed;
  inset: 0;
  z-index: 140;
  background: #0f172a33;
}
.ask-drawer {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  z-index: 150;
  display: flex;
  flex-direction: column;
  width: min(460px, 100vw);
  background: var(--surface);
  border-left: 1px solid var(--border);
  box-shadow: var(--shadow-lg);
  animation: ask-in 0.18s ease-out;
}
@keyframes ask-in {
  from {
    transform: translateX(24px);
    opacity: 0;
  }
}
.ask-head {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: calc(14px + env(safe-area-inset-top, 0px)) 14px 14px 18px;
  border-bottom: 1px solid var(--border);
}
.ask-head .grow {
  display: grid;
  min-width: 0;
}
.ask-head small {
  overflow: hidden;
  color: var(--muted);
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ask-avatar {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border-radius: 11px;
  color: #fff;
  background: linear-gradient(135deg, #6d4fd0, #3d7bb8);
  flex: none;
}
.ask-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 16px 18px;
  overflow-y: auto;
  background: var(--surface-2);
}
.ask-suggestions {
  display: grid;
  gap: 6px;
}
.ask-suggestions button {
  padding: 9px 12px;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--surface);
  color: inherit;
  font: inherit;
  font-size: 14px;
  text-align: left;
  cursor: pointer;
}
.ask-suggestions button:hover {
  border-color: #6d4fd0;
  color: #6d4fd0;
}
.ask-sources {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  margin-top: 8px;
  font-size: 12px;
  color: var(--muted);
}
.ask-source {
  display: inline-flex;
  gap: 4px;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--surface-2);
  color: inherit;
}
.ask-input {
  display: flex;
  gap: 8px;
  align-items: flex-end;
  padding: 12px 14px 8px;
  border-top: 1px solid var(--border);
}
.ask-input textarea {
  flex: 1;
  resize: none;
  max-height: 140px;
  font: inherit;
}
.ask-send {
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  border: 0;
  border-radius: 12px;
  color: #fff;
  background: #6d4fd0;
  cursor: pointer;
  flex: none;
}
.ask-send:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.ask-foot {
  padding: 0 16px calc(12px + env(safe-area-inset-bottom, 0px));
  font-size: 12px;
  color: var(--muted);
}
@media (prefers-reduced-motion: reduce) {
  .ask-drawer {
    animation: none;
  }
}
</style>
