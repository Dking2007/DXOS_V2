<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { BookOpen, Bot, Check, Copy, RotateCcw, SendHorizontal, Settings2, Sparkles, X } from 'lucide-vue-next'
import type { AssistantReply, AssistantStatus } from '@dx/web-shared/types.ts'
import { errorText } from '@dx/web-shared/api.ts'
import { api } from '../api'
import { useSession } from '../stores/session'
import AssistantText from './AssistantText.vue'
import './assistant.css'
import { assistantOpen, historyFor, type ChatTurn } from './state'

const session = useSession()
const route = useRoute()
const queryClient = useQueryClient()
const status = useQuery({
  queryKey: ['assistant-status'],
  queryFn: () => api.request<AssistantStatus>('/assistant'),
  enabled: computed(() => !!session.user),
  staleTime: 60_000,
})
const ready = computed(() => !!status.data.value?.ready)
const visible = computed(() => ready.value || !!status.data.value?.can_manage)
// The chat page and the flow canvas keep their bottom corner; the palette still opens it.
const showButton = computed(() => visible.value && !route.meta.bleed && !route.meta.wide)

const storageKey = computed(() => `dx-assistant-chat:${session.user?.id ?? ''}`)
const turns = ref<ChatTurn[]>([])
function load() {
  try {
    const saved = window.sessionStorage.getItem(storageKey.value)
    turns.value = saved ? (JSON.parse(saved) as ChatTurn[]) : []
  } catch {
    turns.value = []
  }
}
function save() {
  try {
    window.sessionStorage.setItem(storageKey.value, JSON.stringify(turns.value.slice(-40)))
  } catch {
    // Private windows may refuse storage; the conversation still works for this page.
  }
}
watch(storageKey, load, { immediate: true })

const draft = ref('')
const busy = ref(false)
const error = ref('')
const copied = ref(-1)
const remaining = ref<number | null>(null)
const scroller = ref<HTMLElement>()
const input = ref<HTMLTextAreaElement>()

async function scrollDown() {
  await nextTick()
  scroller.value?.scrollTo({ top: scroller.value.scrollHeight })
}
watch(assistantOpen, async (open) => {
  if (!open) return
  await status.refetch()
  remaining.value = status.data.value?.remaining ?? null
  await scrollDown()
  input.value?.focus()
})

async function send(text = draft.value) {
  const question = text.trim()
  if (!question || busy.value || !ready.value) return
  error.value = ''
  turns.value.push({ role: 'user', content: question })
  draft.value = ''
  busy.value = true
  save()
  await scrollDown()
  try {
    const reply = await api.request<AssistantReply>('/assistant/chat', {
      method: 'POST',
      body: JSON.stringify({ messages: historyFor(turns.value) }),
    })
    turns.value.push({ role: 'assistant', content: reply.answer, sources: reply.sources, truncated: reply.truncated })
    remaining.value = reply.remaining
    save()
  } catch (cause) {
    error.value = errorText(cause)
    // Put the question back so it can be sent again after fixing the problem.
    turns.value.pop()
    draft.value = question
    save()
  } finally {
    busy.value = false
    await scrollDown()
    input.value?.focus()
  }
}
function reset() {
  turns.value = []
  error.value = ''
  save()
  input.value?.focus()
}
async function copy(index: number) {
  try {
    await navigator.clipboard.writeText(turns.value[index].content)
    copied.value = index
    window.setTimeout(() => (copied.value = -1), 1500)
  } catch {
    // Clipboard access can be denied; nothing else to do.
  }
}
function onKey(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault()
    void send()
  }
}
function onGlobalKey(event: KeyboardEvent) {
  if (event.key === 'Escape' && assistantOpen.value) assistantOpen.value = false
}
// On a phone the round button floats over list rows; it slides aside while the page scrolls
// down and comes back as soon as the person scrolls up.
const tucked = ref(false)
let lastY = 0
function onScroll() {
  const y = window.scrollY
  if (Math.abs(y - lastY) < 8) return
  tucked.value = y > lastY && y > 80
  lastY = y
}
onMounted(() => {
  document.addEventListener('keydown', onGlobalKey)
  window.addEventListener('scroll', onScroll, { passive: true })
})
onBeforeUnmount(() => {
  document.removeEventListener('keydown', onGlobalKey)
  window.removeEventListener('scroll', onScroll)
})
watch(
  () => route.fullPath,
  () => queryClient.invalidateQueries({ queryKey: ['assistant-status'] }),
)
</script>
<template>
  <button
    v-if="showButton && !assistantOpen"
    type="button"
    class="assistant-fab"
    :class="{ tucked }"
    aria-label="Mở trợ lý AI"
    title="Hỏi trợ lý AI"
    @click="assistantOpen = true"
  >
    <Sparkles :size="24" />
  </button>
  <Transition name="assistant-pop">
    <section v-if="assistantOpen && visible" class="assistant-panel" role="dialog" aria-label="Trợ lý AI">
      <header class="assistant-head">
        <span class="assistant-avatar" aria-hidden="true"><Bot :size="20" /></span>
        <div class="grow">
          <strong>Trợ lý Desktiny</strong>
          <small>{{ ready ? 'Quy trình & cách dùng phần mềm' : 'Chưa sẵn sàng' }}</small>
        </div>
        <button
          v-if="turns.length"
          class="icon-button"
          type="button"
          aria-label="Bắt đầu cuộc trò chuyện mới"
          title="Cuộc trò chuyện mới"
          @click="reset"
        >
          <RotateCcw :size="17" />
        </button>
        <RouterLink
          v-if="status.data.value?.can_manage"
          to="/assistant"
          class="icon-button"
          aria-label="Cài đặt trợ lý"
          title="Cài đặt trợ lý"
          @click="assistantOpen = false"
          ><Settings2 :size="17"
        /></RouterLink>
        <button class="icon-button" type="button" aria-label="Đóng trợ lý" title="Đóng (Esc)" @click="assistantOpen = false">
          <X :size="19" />
        </button>
      </header>
      <div ref="scroller" class="assistant-body" aria-live="polite">
        <div v-if="!ready" class="assistant-setup">
          <Settings2 :size="26" />
          <strong>Trợ lý chưa được bật</strong>
          <p>Bật trợ lý, thêm một dịch vụ AI và viết vài bài kiến thức để mọi người bắt đầu hỏi.</p>
          <RouterLink to="/assistant" class="button small" @click="assistantOpen = false">Mở cài đặt trợ lý</RouterLink>
        </div>
        <template v-else>
          <div class="assistant-msg bot">
            <AssistantText :text="status.data.value?.welcome ?? ''" />
          </div>
          <div v-if="!turns.length && status.data.value?.suggestions.length" class="assistant-suggestions">
            <button v-for="item in status.data.value.suggestions" :key="item" type="button" @click="send(item)">
              {{ item }}
            </button>
          </div>
          <template v-for="(turn, index) in turns" :key="index">
            <div v-if="turn.role === 'user'" class="assistant-msg me">{{ turn.content }}</div>
            <div v-else class="assistant-msg bot">
              <AssistantText :text="turn.content" />
              <p v-if="turn.truncated" class="assistant-note">Câu trả lời bị cắt vì quá dài. Hãy hỏi cụ thể hơn.</p>
              <div v-if="turn.sources?.length" class="assistant-sources">
                <BookOpen :size="13" />
                <span v-for="source in turn.sources" :key="source.id" :title="source.title"
                  >[{{ source.n }}] {{ source.title }}</span
                >
              </div>
              <button
                type="button"
                class="assistant-copy"
                :aria-label="copied === index ? 'Đã chép' : 'Chép câu trả lời'"
                @click="copy(index)"
              >
                <Check v-if="copied === index" :size="13" /><Copy v-else :size="13" />{{
                  copied === index ? 'Đã chép' : 'Chép'
                }}
              </button>
            </div>
          </template>
          <div v-if="busy" class="assistant-msg bot typing" role="status" aria-label="Trợ lý đang trả lời">
            <i /><i /><i />
          </div>
          <p v-if="error" class="assistant-error" role="alert">{{ error }}</p>
        </template>
      </div>
      <form v-if="ready" class="assistant-input" @submit.prevent="send()">
        <textarea
          ref="input"
          v-model="draft"
          rows="1"
          maxlength="2000"
          placeholder="Nhập câu hỏi… (Enter để gửi)"
          aria-label="Câu hỏi cho trợ lý"
          @keydown="onKey"
        />
        <button class="assistant-send" type="submit" :disabled="busy || !draft.trim()" aria-label="Gửi câu hỏi">
          <SendHorizontal :size="18" />
        </button>
      </form>
      <footer v-if="ready" class="assistant-foot">
        <span>Có thể nhầm — đối chiếu văn bản chính thức.</span>
        <span v-if="remaining !== null" :title="`Còn ${remaining} câu hỏi hôm nay`">Còn {{ remaining }} câu</span>
      </footer>
    </section>
  </Transition>
</template>
