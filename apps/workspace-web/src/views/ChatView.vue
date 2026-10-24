<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import {
  ArrowLeft,
  AtSign,
  Check,
  CheckCheck,
  Download,
  ExternalLink,
  ListPlus,
  LogOut,
  MessageSquarePlus,
  Paperclip,
  Pencil,
  Reply,
  Search,
  SendHorizontal,
  SmilePlus,
  Trash2,
  UploadCloud,
  UserPlus,
  X,
} from 'lucide-vue-next'
import { api } from '../api'
import { useSession } from '../stores/session'
import { errorText, newIntent } from '@dx/web-shared/api.ts'
import type { Page } from '@dx/web-shared/api.ts'
import type {
  ChatAttachment,
  ChatMessage,
  Conversation,
  Department,
  Task,
  User,
} from '@dx/web-shared/types.ts'
import StatePanel from '@dx/web-shared/components/StatePanel.vue'
import ModalDialog from '@dx/web-shared/components/ModalDialog.vue'
import TaskCreateDialog from '../components/TaskCreateDialog.vue'
import MessageAttachments from '../chat/MessageAttachments.vue'
import FilePreview from '../components/FilePreview.vue'
import {
  ACCEPT,
  MAX_FILE_BYTES,
  avatarColor,
  dayLabel,
  fileSize,
  initials,
  listTime,
  timeLabel,
  uploadAttachment,
} from '../chat/upload'
import '../chat/chat.css'
const EMOJI = ['👍', '❤️', '😂', '🎉', '😮', '🙏']
const route = useRoute()
const router = useRouter()
const queryClient = useQueryClient()
const session = useSession()
const activeId = ref(String(route.query.c ?? ''))
const filter = ref('')
const list = useQuery({
  queryKey: ['conversations'],
  queryFn: () => api.request<Page<Conversation> & { unread_total: number }>('/conversations'),
  refetchInterval: 8_000,
})
const visibleList = computed(() =>
  (list.data.value?.items ?? []).filter((item) => item.title.toLowerCase().includes(filter.value.toLowerCase())),
)
watch(
  () => list.data.value?.items,
  (items) => {
    if (!activeId.value && items?.length && window.innerWidth > 900) activeId.value = items[0].id
  },
)
const conversation = useQuery({
  queryKey: computed(() => ['conversation', activeId.value]),
  queryFn: () => api.request<Conversation>(`/conversations/${activeId.value}`),
  enabled: computed(() => !!activeId.value),
  // Members' read cursors drive the "seen" marks.
  refetchInterval: 8_000,
})
interface MessagePage {
  items: ChatMessage[]
  last_seq: number
  has_more_before: boolean
}
const latest = useQuery({
  queryKey: computed(() => ['messages', activeId.value]),
  queryFn: () => api.request<MessagePage>(`/conversations/${activeId.value}/messages?limit=50`),
  enabled: computed(() => !!activeId.value),
  // Polling is the delivery path in this release; REST stays the source of truth either way.
  refetchInterval: 4_000,
})
const older = ref<ChatMessage[]>([])
const hasMoreBefore = ref(false)
watch(
  () => latest.data.value,
  (value) => {
    if (value && !older.value.length) hasMoreBefore.value = value.has_more_before
  },
)
const messages = computed(() => {
  const bySeq = new Map<number, ChatMessage>()
  for (const item of [...older.value, ...(latest.data.value?.items ?? [])]) bySeq.set(item.seq, item)
  return [...bySeq.values()].sort((a, b) => a.seq - b.seq)
})
/** Consecutive messages from one person within five minutes read as one block. */
const rows = computed(() =>
  messages.value.map((message, index) => {
    const previous = messages.value[index - 1]
    const next = messages.value[index + 1]
    const day = dayLabel(message.created_at)
    const close = (a?: ChatMessage, b?: ChatMessage) =>
      !!a &&
      !!b &&
      a.sender_id === b.sender_id &&
      dayLabel(a.created_at) === dayLabel(b.created_at) &&
      Math.abs(new Date(b.created_at).getTime() - new Date(a.created_at).getTime()) < 5 * 60_000
    return {
      message,
      day: !previous || dayLabel(previous.created_at) !== day ? day : null,
      first: !close(previous, message),
      last: !close(message, next),
    }
  }),
)
const others = computed(() =>
  (conversation.data.value?.members ?? []).filter((m) => m.user_id !== session.user?.id),
)
const lastMine = computed(() => [...messages.value].reverse().find((m) => m.mine && !m.deleted))
const seenText = computed(() => {
  const mine = lastMine.value
  if (!mine || mine.seq !== messages.value.at(-1)?.seq) return ''
  const readers = others.value.filter((m) => m.last_read_seq >= mine.seq)
  if (!readers.length) return 'Đã gửi'
  if (conversation.data.value?.kind === 'direct') return 'Đã xem'
  return readers.length === others.value.length ? 'Mọi người đã xem' : `${readers.length} người đã xem`
})
async function loadOlder() {
  const first = messages.value[0]
  if (!first) return
  const page = await api.request<MessagePage>(
    `/conversations/${activeId.value}/messages?before_seq=${first.seq}&limit=50`,
  )
  older.value = [...page.items, ...older.value]
  hasMoreBefore.value = page.has_more_before
}
const scroller = ref<HTMLElement>()
/** Follow new content only while the reader is at the bottom, not while reading history. */
const stick = ref(true)
function onScroll() {
  const element = scroller.value
  if (element) stick.value = element.scrollHeight - element.scrollTop - element.clientHeight < 140
}
function toBottom() {
  if (scroller.value && stick.value) scroller.value.scrollTop = scroller.value.scrollHeight
}
// Pictures and videos grow the page after they load; keep the newest message in view.
function onMediaLoad() {
  toBottom()
}
let lastRead = 0
watch(
  () => messages.value.at(-1)?.seq,
  async (seq) => {
    await nextTick()
    toBottom()
    // The read cursor moves only when the page is actually visible to the reader.
    if (seq && seq > lastRead && document.visibilityState === 'visible') {
      lastRead = seq
      await api.request(`/conversations/${activeId.value}/read-cursor`, {
        method: 'POST',
        body: JSON.stringify({ seq }),
      })
      await queryClient.invalidateQueries({ queryKey: ['conversations'] })
    }
  },
)

// ---- Composer ----
const draft = ref('')
const mentionIds = ref<string[]>([])
const replyTo = ref<ChatMessage | null>(null)
const editing = ref<ChatMessage | null>(null)
const showMention = ref(false)
const showEmoji = ref(false)
const error = ref<unknown>(null)
const sending = ref(false)
const textarea = ref<HTMLTextAreaElement>()
interface Pending {
  key: string
  file: File
  preview: string | null
  progress: number
  attachment: ChatAttachment | null
  error: string | null
  abort: () => void
}
const pending = ref<Pending[]>([])
const uploading = computed(() => pending.value.some((p) => !p.attachment && !p.error))
const canSend = computed(
  () =>
    !sending.value &&
    !uploading.value &&
    (draft.value.trim().length > 0 || pending.value.some((p) => p.attachment)) &&
    !pending.value.some((p) => p.error),
)
function resetComposer() {
  draft.value = ''
  mentionIds.value = []
  replyTo.value = null
  editing.value = null
  for (const item of pending.value) if (item.preview) URL.revokeObjectURL(item.preview)
  pending.value = []
}
watch(activeId, (value) => {
  older.value = []
  lastRead = 0
  stick.value = true
  resetComposer()
  router.replace({ query: value ? { c: value } : {} })
})
onBeforeUnmount(resetComposer)
function addFiles(files: FileList | File[]) {
  if (!activeId.value || editing.value) return
  for (const file of Array.from(files)) {
    if (pending.value.length >= 10) {
      error.value = new Error('Mỗi tin nhắn gửi tối đa 10 tệp.')
      break
    }
    const item: Pending = {
      key: newIntent(),
      file,
      preview: file.type.startsWith('image/') ? URL.createObjectURL(file) : null,
      progress: 0,
      attachment: null,
      error: null,
      abort: () => {},
    }
    pending.value = [...pending.value, item]
    const entry = pending.value.at(-1)!
    if (file.size > MAX_FILE_BYTES) {
      entry.error = `Vượt ${fileSize(MAX_FILE_BYTES)}`
      continue
    }
    const job = uploadAttachment(activeId.value, file, session.user?.csrf_token ?? '', (fraction) => {
      entry.progress = fraction
    })
    entry.abort = job.abort
    job.promise.then(
      (attachment) => (entry.attachment = attachment),
      (cause) => (entry.error = errorText(cause)),
    )
  }
}
function removePending(item: Pending) {
  item.abort()
  if (item.preview) URL.revokeObjectURL(item.preview)
  pending.value = pending.value.filter((p) => p.key !== item.key)
}
const fileInput = ref<HTMLInputElement>()
function pickFiles(event: Event) {
  const input = event.target as HTMLInputElement
  if (input.files) addFiles(input.files)
  input.value = ''
}
function onPaste(event: ClipboardEvent) {
  const files = Array.from(event.clipboardData?.files ?? [])
  if (files.length) {
    event.preventDefault()
    addFiles(files)
  }
}
const dragging = ref(false)
let dragDepth = 0
function onDragEnter(event: DragEvent) {
  if (!event.dataTransfer?.types.includes('Files')) return
  dragDepth += 1
  dragging.value = true
}
function onDragLeave() {
  dragDepth = Math.max(0, dragDepth - 1)
  if (!dragDepth) dragging.value = false
}
function onDrop(event: DragEvent) {
  dragDepth = 0
  dragging.value = false
  if (event.dataTransfer?.files.length) addFiles(event.dataTransfer.files)
}
function mention(member: { user_id: string; display_name: string }) {
  draft.value = `${draft.value}${draft.value && !draft.value.endsWith(' ') ? ' ' : ''}@${member.display_name} `
  if (!mentionIds.value.includes(member.user_id)) mentionIds.value.push(member.user_id)
  showMention.value = false
  textarea.value?.focus()
}
function addEmoji(emoji: string) {
  draft.value += emoji
  showEmoji.value = false
  textarea.value?.focus()
}
function autosize() {
  const element = textarea.value
  if (!element) return
  element.style.height = 'auto'
  element.style.height = `${Math.min(element.scrollHeight, 160)}px`
}
watch(draft, () => nextTick(autosize))
async function send() {
  if (!canSend.value || !activeId.value) return
  sending.value = true
  error.value = null
  try {
    if (editing.value) {
      await api.request(`/messages/${editing.value.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ body: draft.value.trim() }),
      })
    } else {
      await api.request(`/conversations/${activeId.value}/messages`, {
        method: 'POST',
        body: JSON.stringify({
          client_message_id: newIntent(),
          body: draft.value.trim(),
          reply_to_id: replyTo.value?.id ?? null,
          mention_ids: mentionIds.value,
          attachment_ids: pending.value.filter((p) => p.attachment).map((p) => p.attachment!.id),
        }),
      })
    }
    resetComposer()
    stick.value = true
    await latest.refetch()
    await queryClient.invalidateQueries({ queryKey: ['conversations'] })
  } catch (cause) {
    error.value = cause
  } finally {
    sending.value = false
  }
}
function onKey(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault()
    void send()
  }
  if (event.key === 'Escape') resetComposer()
}
async function react(message: ChatMessage, emoji: string) {
  await api.request(`/messages/${message.id}/reactions/me`, {
    method: 'PUT',
    body: JSON.stringify({ emoji }),
  })
  picker.value = null
  await latest.refetch()
}
async function remove(message: ChatMessage) {
  if (!window.confirm('Xóa tin nhắn này? Tệp đính kèm cũng không còn xem được.')) return
  await api.request(`/messages/${message.id}`, { method: 'DELETE' })
  older.value = older.value.map((m) => (m.id === message.id ? { ...m, deleted: true, body: '', attachments: [] } : m))
  await latest.refetch()
}
function startEdit(message: ChatMessage) {
  for (const item of pending.value) removePending(item)
  editing.value = message
  replyTo.value = null
  draft.value = message.body
  textarea.value?.focus()
}
function startReply(message: ChatMessage) {
  replyTo.value = message
  editing.value = null
  textarea.value?.focus()
}
const picker = ref<string | null>(null)
const taskFrom = ref<ChatMessage | null>(null)
async function taskCreated(task: Task) {
  taskFrom.value = null
  await router.push(`/tasks/${task.id}`)
}
const lightbox = ref<ChatAttachment | null>(null)
const filePreview = ref<ChatAttachment | null>(null)
async function previewSource(item: ChatAttachment) {
  return `${item.url}?download=1`
}
function downloadAttachment(item: ChatAttachment) {
  window.location.assign(`${item.url}?download=1`)
}
function snippet(message: ChatMessage | null) {
  if (!message) return ''
  if (message.deleted) return 'Tin nhắn đã xóa'
  if (message.body) return message.body
  const kinds = message.attachments.map((a) => a.kind)
  if (kinds.every((k) => k === 'image')) return `📷 ${kinds.length > 1 ? `${kinds.length} ảnh` : 'Ảnh'}`
  if (kinds.includes('video')) return '🎬 Video'
  return `📎 ${message.attachments.length} tệp`
}

// ---- New conversation, members ----
const showNew = ref(route.query.new === '1')
watch(
  () => route.query.new,
  (value) => {
    if (value) showNew.value = true
  },
)
const newKind = ref<'direct' | 'group' | 'department'>('direct')
const newTitle = ref('')
const newMembers = ref<string[]>([])
const newDepartment = ref('')
const peopleQuery = ref('')
const users = useQuery({ queryKey: ['users'], queryFn: () => api.request<Page<User>>('/users') })
const departments = useQuery({
  queryKey: ['departments'],
  queryFn: () => api.request<Page<Department>>('/departments'),
  enabled: computed(() => showNew.value),
})
const otherUsers = computed(() =>
  (users.data.value?.items ?? []).filter(
    (user) =>
      user.id !== session.user?.id && user.display_name.toLowerCase().includes(peopleQuery.value.toLowerCase()),
  ),
)
function togglePerson(id: string) {
  if (newKind.value === 'direct') newMembers.value = [id]
  else newMembers.value = newMembers.value.includes(id) ? newMembers.value.filter((x) => x !== id) : [...newMembers.value, id]
}
async function createConversation() {
  error.value = null
  try {
    const created = await api.request<Conversation>('/conversations', {
      method: 'POST',
      body: JSON.stringify({
        kind: newKind.value,
        title: newTitle.value,
        member_ids: newMembers.value,
        department_id: newKind.value === 'department' ? newDepartment.value : null,
      }),
    })
    showNew.value = false
    newTitle.value = ''
    newMembers.value = []
    await queryClient.invalidateQueries({ queryKey: ['conversations'] })
    activeId.value = created.id
  } catch (cause) {
    error.value = cause
  }
}
const showAdd = ref(false)
const addIds = ref<string[]>([])
const addHistory = ref(false)
async function addMembers() {
  error.value = null
  try {
    await api.request(`/conversations/${activeId.value}/members`, {
      method: 'POST',
      body: JSON.stringify({ user_ids: addIds.value, include_history: addHistory.value }),
    })
    showAdd.value = false
    addIds.value = []
    await conversation.refetch()
  } catch (cause) {
    error.value = cause
  }
}
async function leave() {
  if (!window.confirm('Rời khỏi hội thoại này? Bạn sẽ không đọc được lịch sử nữa.')) return
  await api.request(`/conversations/${activeId.value}/members/${session.user?.id}`, { method: 'DELETE' })
  activeId.value = ''
  await queryClient.invalidateQueries({ queryKey: ['conversations'] })
}
const kindLabel: Record<Conversation['kind'], string> = {
  direct: 'Trò chuyện riêng',
  group: 'Nhóm',
  department: 'Kênh phòng ban',
  task: 'Trao đổi công việc',
  case: 'Trao đổi hồ sơ',
}
</script>
<template>
  <div class="chat-shell" :class="{ 'has-active': !!activeId }">
    <aside class="chat-sidebar">
      <header class="chat-sidebar-head">
        <h1>Nhắn tin</h1>
        <button class="icon-button" title="Hội thoại mới" aria-label="Hội thoại mới" @click="showNew = true">
          <MessageSquarePlus :size="19" />
        </button>
      </header>
      <label class="chat-search"
        ><Search :size="16" /><input v-model="filter" type="search" placeholder="Tìm hội thoại" aria-label="Tìm hội thoại"
      /></label>
      <div class="chat-threads">
        <StatePanel
          :loading="list.isPending.value"
          :error="list.error.value"
          :empty="list.data.value?.items.length === 0"
          title="Chưa có hội thoại"
          description="Bắt đầu trò chuyện với đồng nghiệp hoặc mở trao đổi từ một công việc."
          @retry="list.refetch()"
          ><button class="button small" @click="showNew = true"><MessageSquarePlus :size="15" />Hội thoại mới</button></StatePanel
        >
        <button
          v-for="item in visibleList"
          :key="item.id"
          class="chat-thread"
          :class="{ active: item.id === activeId, unread: item.unread > 0 }"
          @click="activeId = item.id"
        >
          <span class="chat-avatar" :style="{ background: avatarColor(item.title) }">{{
            item.kind === 'direct' ? initials(item.title) : kindLabel[item.kind][0]
          }}</span>
          <span class="chat-thread-text">
            <span class="chat-thread-top"
              ><strong>{{ item.title }}</strong
              ><time v-if="item.last_message">{{ listTime(item.last_message.created_at) }}</time></span
            >
            <span class="chat-thread-bottom"
              ><small
                >{{ item.last_message ? `${item.last_message.mine ? 'Bạn: ' : item.kind === 'direct' ? '' : `${item.last_message.sender_name}: `}${snippet(item.last_message)}` : kindLabel[item.kind] }}</small
              ><span v-if="item.unread" class="chat-unread">{{ item.unread > 99 ? '99+' : item.unread }}</span></span
            >
          </span>
        </button>
      </div>
    </aside>

    <section
      class="chat-main"
      @dragenter.prevent="onDragEnter"
      @dragover.prevent
      @dragleave="onDragLeave"
      @drop.prevent="onDrop"
    >
      <template v-if="activeId && conversation.data.value">
        <header class="chat-main-head">
          <button class="icon-button chat-back" aria-label="Quay lại danh sách" @click="activeId = ''">
            <ArrowLeft :size="19" />
          </button>
          <span class="chat-avatar" :style="{ background: avatarColor(conversation.data.value.title) }">{{
            conversation.data.value.kind === 'direct' ? initials(conversation.data.value.title) : kindLabel[conversation.data.value.kind][0]
          }}</span>
          <div class="grow">
            <strong>{{ conversation.data.value.title }}</strong>
            <small
              >{{ kindLabel[conversation.data.value.kind] }}<template v-if="conversation.data.value.kind !== 'direct'">
                · {{ conversation.data.value.member_count }} thành viên</template
              ></small
            >
          </div>
          <RouterLink
            v-if="conversation.data.value.ref_type"
            :to="`/${conversation.data.value.ref_type === 'task' ? 'tasks' : 'cases'}/${conversation.data.value.ref_id}`"
            class="button ghost small"
            ><ExternalLink :size="14" />Mở {{ conversation.data.value.ref_type === 'task' ? 'công việc' : 'hồ sơ' }}</RouterLink
          >
          <button
            v-if="conversation.data.value.kind !== 'direct' && conversation.data.value.my_role === 'owner'"
            class="icon-button"
            aria-label="Thêm thành viên"
            title="Thêm thành viên"
            @click="showAdd = true"
          >
            <UserPlus :size="18" /></button
          ><button
            v-if="conversation.data.value.kind !== 'direct'"
            class="icon-button"
            aria-label="Rời hội thoại"
            title="Rời hội thoại"
            @click="leave"
          >
            <LogOut :size="18" />
          </button>
        </header>

        <div
          ref="scroller"
          class="chat-scroll"
          @scroll.passive="onScroll"
          @load.capture="onMediaLoad"
          @loadedmetadata.capture="onMediaLoad"
        >
          <button v-if="hasMoreBefore" class="button ghost small chat-older" @click="loadOlder">Xem tin nhắn cũ hơn</button>
          <div v-if="!messages.length && !latest.isPending.value" class="chat-hello">
            <span class="chat-avatar large" :style="{ background: avatarColor(conversation.data.value.title) }">{{
              initials(conversation.data.value.title)
            }}</span>
            <strong>{{ conversation.data.value.title }}</strong>
            <small>Hãy gửi lời chào đầu tiên 👋</small>
          </div>
          <template v-for="row in rows" :key="row.message.id">
            <div v-if="row.day" class="chat-day"><span>{{ row.day }}</span></div>
            <div
              class="chat-row"
              :class="{ mine: row.message.mine, first: row.first, last: row.last }"
            >
              <span
                v-if="!row.message.mine"
                class="chat-avatar small"
                :class="{ hidden: !row.last }"
                :style="{ background: avatarColor(row.message.sender_name) }"
                >{{ initials(row.message.sender_name) }}</span
              >
              <div class="chat-stack">
                <small v-if="!row.message.mine && row.first && conversation.data.value.kind !== 'direct'" class="chat-sender">{{
                  row.message.sender_name
                }}</small>
                <div v-if="row.message.deleted" class="chat-bubble deleted">Tin nhắn đã bị xóa</div>
                <template v-else>
                  <div v-if="row.message.reply_to" class="chat-reply-ref">
                    <Reply :size="12" /> {{ row.message.reply_to.sender_name }}: {{ row.message.reply_to.body || 'Tin nhắn đã xóa' }}
                  </div>
                  <MessageAttachments
                    v-if="row.message.attachments.length"
                    :items="row.message.attachments"
                    :mine="row.message.mine"
                    @open="(item) => (lightbox = item)"
                    @preview="(item) => (filePreview = item)"
                  />
                  <div v-if="row.message.body" class="chat-bubble">
                    <p>{{ row.message.body }}</p>
                    <span class="chat-time"
                      >{{ timeLabel(row.message.created_at) }}<template v-if="row.message.edited_at"> · đã sửa</template></span
                    >
                  </div>
                  <span v-else class="chat-time outside">{{ timeLabel(row.message.created_at) }}</span>
                  <div v-if="Object.keys(row.message.reactions).length" class="chat-reactions">
                    <button
                      v-for="(people, emoji) in row.message.reactions"
                      :key="emoji"
                      :class="{ mine: people.includes(session.user?.id ?? '') }"
                      @click="react(row.message, String(emoji))"
                    >
                      {{ emoji }} <b>{{ people.length }}</b>
                    </button>
                  </div>
                </template>
                <small v-if="row.message.id === lastMine?.id && seenText" class="chat-seen"
                  ><CheckCheck v-if="seenText !== 'Đã gửi'" :size="13" /><Check v-else :size="13" />{{ seenText }}</small
                >
              </div>
              <div v-if="!row.message.deleted" class="chat-tools">
                <button aria-label="Thả cảm xúc" title="Thả cảm xúc" @click="picker = picker === row.message.id ? null : row.message.id">
                  <SmilePlus :size="15" /></button
                ><button aria-label="Trả lời" title="Trả lời" @click="startReply(row.message)"><Reply :size="15" /></button
                ><button aria-label="Tạo việc từ tin nhắn" title="Tạo việc" @click="taskFrom = row.message"><ListPlus :size="15" /></button
                ><template v-if="row.message.mine"
                  ><button v-if="row.message.body" aria-label="Sửa" title="Sửa" @click="startEdit(row.message)"><Pencil :size="15" /></button
                  ><button aria-label="Xóa" title="Xóa" @click="remove(row.message)"><Trash2 :size="15" /></button
                ></template>
                <div v-if="picker === row.message.id" class="chat-emoji-pop">
                  <button v-for="emoji in EMOJI" :key="emoji" @click="react(row.message, emoji)">{{ emoji }}</button>
                </div>
              </div>
            </div>
          </template>
        </div>

        <footer class="chat-composer">
          <div v-if="error" class="notice error chat-error">
            {{ errorText(error) }}<button class="icon-button" aria-label="Đóng" @click="error = null"><X :size="14" /></button>
          </div>
          <div v-if="replyTo || editing" class="chat-context">
            <span v-if="editing"><Pencil :size="14" /> Đang sửa tin nhắn</span>
            <span v-else
              ><Reply :size="14" /> Trả lời <b>{{ replyTo?.sender_name }}</b>: {{ snippet(replyTo).slice(0, 80) }}</span
            >
            <button class="icon-button" aria-label="Bỏ" @click="resetComposer"><X :size="15" /></button>
          </div>
          <div v-if="pending.length" class="chat-pending">
            <div v-for="item in pending" :key="item.key" class="chat-pending-item" :class="{ failed: item.error }">
              <img v-if="item.preview" :src="item.preview" alt="" />
              <span v-else class="chat-pending-file"><Paperclip :size="16" /><small>{{ item.file.name }}</small></span>
              <span v-if="!item.attachment && !item.error" class="chat-progress"
                ><span :style="{ width: `${Math.round(item.progress * 100)}%` }"
              /></span>
              <span v-if="item.error" class="chat-pending-error" :title="item.error">{{ item.error }}</span>
              <button class="chat-pending-remove" aria-label="Bỏ tệp" @click="removePending(item)"><X :size="12" /></button>
            </div>
          </div>
          <form class="chat-input" @submit.prevent="send">
            <input ref="fileInput" type="file" multiple :accept="ACCEPT" hidden @change="pickFiles" />
            <button
              type="button"
              class="icon-button"
              aria-label="Đính kèm ảnh, video, tệp"
              title="Đính kèm ảnh, video, tệp"
              :disabled="!!editing"
              @click="fileInput?.click()"
            >
              <Paperclip :size="19" />
            </button>
            <div class="chat-pop-anchor">
              <button
                type="button"
                class="icon-button"
                aria-label="Nhắc tên"
                title="Nhắc tên"
                :disabled="!others.length"
                @click="showMention = !showMention"
              >
                <AtSign :size="19" />
              </button>
              <div v-if="showMention" class="chat-menu">
                <button v-for="member in others" :key="member.user_id" type="button" @click="mention(member)">
                  <span class="chat-avatar tiny" :style="{ background: avatarColor(member.display_name) }">{{ initials(member.display_name) }}</span>
                  {{ member.display_name }}
                </button>
              </div>
            </div>
            <textarea
              ref="textarea"
              v-model="draft"
              rows="1"
              :placeholder="editing ? 'Sửa tin nhắn…' : 'Nhập tin nhắn…'"
              title="Enter để gửi, Shift+Enter xuống dòng. Dán hoặc kéo thả ảnh, video, tệp để đính kèm."
              aria-label="Nội dung tin nhắn"
              @keydown="onKey"
              @paste="onPaste"
            />
            <div class="chat-pop-anchor">
              <button type="button" class="icon-button" aria-label="Chèn biểu tượng cảm xúc" @click="showEmoji = !showEmoji">
                <SmilePlus :size="19" />
              </button>
              <div v-if="showEmoji" class="chat-menu emoji">
                <button v-for="emoji in ['😀', '😂', '😍', '🥰', '😎', '🤔', '😢', '😡', '👍', '👏', '🙏', '🎉', '❤️', '🔥', '✅', '⏰']" :key="emoji" type="button" @click="addEmoji(emoji)">
                  {{ emoji }}
                </button>
              </div>
            </div>
            <button class="chat-send" :disabled="!canSend" :aria-label="editing ? 'Lưu' : 'Gửi'" :title="uploading ? 'Đang tải tệp lên…' : ''">
              <SendHorizontal :size="18" />
            </button>
          </form>
        </footer>
        <div v-if="dragging" class="chat-drop"><UploadCloud :size="38" /><strong>Thả để gửi ảnh, video hoặc tệp</strong></div>
      </template>
      <div v-else class="chat-empty-state">
        <MessageSquarePlus :size="40" />
        <strong>Chọn một hội thoại</strong>
        <span>Hoặc tạo hội thoại mới để bắt đầu trao đổi.</span>
        <button class="button" @click="showNew = true"><MessageSquarePlus :size="16" />Hội thoại mới</button>
      </div>
    </section>
  </div>

  <FilePreview
    v-if="filePreview"
    :key="filePreview.id"
    :name="filePreview.name"
    :mime="filePreview.mime"
    :source="() => previewSource(filePreview!)"
    :download="() => downloadAttachment(filePreview!)"
    @close="filePreview = null"
  />
  <div v-if="lightbox" class="chat-lightbox" role="dialog" aria-label="Xem ảnh" @click.self="lightbox = null">
    <img :src="lightbox.url" :alt="lightbox.name" />
    <div class="chat-lightbox-bar">
      <span>{{ lightbox.name }} · {{ fileSize(lightbox.size) }}</span>
      <a class="button secondary small" :href="`${lightbox.url}?download=1`" :download="lightbox.name"><Download :size="15" />Tải về</a>
      <button class="button secondary small" @click="lightbox = null"><X :size="15" />Đóng</button>
    </div>
  </div>

  <ModalDialog v-if="showNew" title="Hội thoại mới" @close="showNew = false">
    <form class="stack" @submit.prevent="createConversation">
      <div class="segmented chat-kind">
        <button
          v-for="kind in [
            { value: 'direct', label: 'Trò chuyện riêng' },
            { value: 'group', label: 'Nhóm' },
            { value: 'department', label: 'Kênh phòng ban' },
          ] as const"
          :key="kind.value"
          type="button"
          :class="{ active: newKind === kind.value }"
          @click="
            () => {
              newKind = kind.value
              newMembers = []
            }
          "
        >
          {{ kind.label }}
        </button>
      </div>
      <div v-if="newKind !== 'direct'" class="field">
        <label for="conv-title">Tên {{ newKind === 'group' ? 'nhóm' : 'kênh' }}</label
        ><input id="conv-title" v-model="newTitle" :required="newKind === 'group'" maxlength="200" />
      </div>
      <template v-if="newKind !== 'department'">
        <label class="chat-search" style="margin: 0"
          ><Search :size="16" /><input v-model="peopleQuery" type="search" placeholder="Tìm đồng nghiệp" aria-label="Tìm đồng nghiệp"
        /></label>
        <div class="chat-people">
          <button
            v-for="user in otherUsers"
            :key="user.id"
            type="button"
            class="chat-person"
            :class="{ active: newMembers.includes(user.id) }"
            @click="togglePerson(user.id)"
          >
            <span class="chat-avatar small" :style="{ background: avatarColor(user.display_name) }">{{ initials(user.display_name) }}</span>
            <span class="grow">{{ user.display_name }}</span>
            <Check v-if="newMembers.includes(user.id)" :size="16" />
          </button>
        </div>
      </template>
      <div v-else class="field">
        <label for="conv-dept">Phòng ban</label
        ><select id="conv-dept" v-model="newDepartment" required>
          <option value="">Chọn phòng ban</option>
          <option v-for="dept in departments.data.value?.items" :key="dept.id" :value="dept.id">{{ dept.name }}</option>
        </select>
        <small>Chỉ lãnh đạo phòng hoặc quản trị được tạo kênh phòng ban.</small>
      </div>
      <div v-if="error" class="notice error">{{ errorText(error) }}</div>
      <div class="form-actions">
        <button type="button" class="button secondary" @click="showNew = false">Hủy</button
        ><button class="button" :disabled="newKind !== 'department' && !newMembers.length">Bắt đầu trò chuyện</button>
      </div>
    </form>
  </ModalDialog>
  <ModalDialog v-if="showAdd" title="Thêm thành viên" @close="showAdd = false">
    <form class="stack" @submit.prevent="addMembers">
      <div class="chat-people">
        <button
          v-for="user in otherUsers.filter((u) => !conversation.data.value?.members?.some((m) => m.user_id === u.id))"
          :key="user.id"
          type="button"
          class="chat-person"
          :class="{ active: addIds.includes(user.id) }"
          @click="addIds = addIds.includes(user.id) ? addIds.filter((x) => x !== user.id) : [...addIds, user.id]"
        >
          <span class="chat-avatar small" :style="{ background: avatarColor(user.display_name) }">{{ initials(user.display_name) }}</span>
          <span class="grow">{{ user.display_name }}</span>
          <Check v-if="addIds.includes(user.id)" :size="16" />
        </button>
      </div>
      <label class="checkbox-label"><input v-model="addHistory" type="checkbox" />Cho xem toàn bộ lịch sử trước khi tham gia</label>
      <div v-if="error" class="notice error">{{ errorText(error) }}</div>
      <div class="form-actions">
        <button type="button" class="button secondary" @click="showAdd = false">Hủy</button
        ><button class="button" :disabled="!addIds.length">Thêm</button>
      </div>
    </form>
  </ModalDialog>
  <TaskCreateDialog
    v-if="taskFrom"
    heading="Tạo việc từ tin nhắn"
    :default-title="(taskFrom.body || snippet(taskFrom)).slice(0, 120)"
    :source="{ type: 'message', id: taskFrom.id, label: (taskFrom.body || snippet(taskFrom)).slice(0, 200) }"
    @close="taskFrom = null"
    @created="taskCreated"
  />
</template>
