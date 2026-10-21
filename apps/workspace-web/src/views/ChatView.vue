<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import {
  AtSign,
  ListPlus,
  MessageSquarePlus,
  Pencil,
  Reply,
  Search,
  SendHorizontal,
  SmilePlus,
  Trash2,
  UserPlus,
  Users,
  X,
} from 'lucide-vue-next'
import { api } from '../api'
import { useSession } from '../stores/session'
import { errorText, formatDate, newIntent } from '@dx/web-shared/api.ts'
import type { Page } from '@dx/web-shared/api.ts'
import type { ChatMessage, Conversation, Department, Task, User } from '@dx/web-shared/types.ts'
import StatePanel from '@dx/web-shared/components/StatePanel.vue'
import ModalDialog from '@dx/web-shared/components/ModalDialog.vue'
import TaskCreateDialog from '../components/TaskCreateDialog.vue'
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
  (list.data.value?.items ?? []).filter((item) =>
    item.title.toLowerCase().includes(filter.value.toLowerCase()),
  ),
)
watch(
  () => list.data.value?.items,
  (items) => {
    if (!activeId.value && items?.length && window.innerWidth > 900) activeId.value = items[0].id
  },
)
watch(activeId, (value) => {
  older.value = []
  replyTo.value = null
  editing.value = null
  router.replace({ query: value ? { c: value } : {} })
})
const conversation = useQuery({
  queryKey: computed(() => ['conversation', activeId.value]),
  queryFn: () => api.request<Conversation>(`/conversations/${activeId.value}`),
  enabled: computed(() => !!activeId.value),
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
let lastRead = 0
watch(
  () => messages.value.at(-1)?.seq,
  async (seq) => {
    await nextTick()
    if (scroller.value) scroller.value.scrollTop = scroller.value.scrollHeight
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
watch(activeId, () => (lastRead = 0))
const draft = ref('')
const mentionIds = ref<string[]>([])
const replyTo = ref<ChatMessage | null>(null)
const editing = ref<ChatMessage | null>(null)
const showMention = ref(false)
const error = ref<unknown>(null)
const sending = ref(false)
const members = computed(() =>
  (conversation.data.value?.members ?? []).filter((m) => m.user_id !== session.user?.id),
)
function mention(member: { user_id: string; display_name: string }) {
  draft.value = `${draft.value}${draft.value && !draft.value.endsWith(' ') ? ' ' : ''}@${member.display_name} `
  if (!mentionIds.value.includes(member.user_id)) mentionIds.value.push(member.user_id)
  showMention.value = false
}
async function send() {
  const body = draft.value.trim()
  if (!body || !activeId.value) return
  sending.value = true
  error.value = null
  try {
    if (editing.value) {
      await api.request(`/messages/${editing.value.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ body }),
      })
      editing.value = null
    } else {
      await api.request(`/conversations/${activeId.value}/messages`, {
        method: 'POST',
        body: JSON.stringify({
          client_message_id: newIntent(),
          body,
          reply_to_id: replyTo.value?.id ?? null,
          mention_ids: mentionIds.value,
        }),
      })
    }
    draft.value = ''
    mentionIds.value = []
    replyTo.value = null
    await latest.refetch()
    await queryClient.invalidateQueries({ queryKey: ['conversations'] })
  } catch (cause) {
    error.value = cause
  } finally {
    sending.value = false
  }
}
function onKey(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    void send()
  }
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
  if (!window.confirm('Xóa tin nhắn này?')) return
  await api.request(`/messages/${message.id}`, { method: 'DELETE' })
  older.value = older.value.map((m) => (m.id === message.id ? { ...m, deleted: true, body: '' } : m))
  await latest.refetch()
}
function startEdit(message: ChatMessage) {
  editing.value = message
  replyTo.value = null
  draft.value = message.body
}
const picker = ref<string | null>(null)
const taskFrom = ref<ChatMessage | null>(null)
async function taskCreated(task: Task) {
  taskFrom.value = null
  await router.push(`/tasks/${task.id}`)
}
// New conversation
const showNew = ref(false)
const newKind = ref<'direct' | 'group' | 'department'>('direct')
const newTitle = ref('')
const newMembers = ref<string[]>([])
const newDepartment = ref('')
const users = useQuery({
  queryKey: ['users'],
  queryFn: () => api.request<Page<User>>('/users'),
})
const departments = useQuery({
  queryKey: ['departments'],
  queryFn: () => api.request<Page<Department>>('/departments'),
  enabled: computed(() => showNew.value),
})
const otherUsers = computed(() =>
  (users.data.value?.items ?? []).filter((user) => user.id !== session.user?.id),
)
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
  await api.request(`/conversations/${activeId.value}/members/${session.user?.id}`, {
    method: 'DELETE',
  })
  activeId.value = ''
  await queryClient.invalidateQueries({ queryKey: ['conversations'] })
}
const kindLabel: Record<Conversation['kind'], string> = {
  direct: 'Riêng',
  group: 'Nhóm',
  department: 'Phòng ban',
  task: 'Công việc',
  case: 'Hồ sơ',
}
function initials(name: string) {
  return name
    .split(' ')
    .slice(-2)
    .map((word) => word[0])
    .join('')
    .toUpperCase()
}
</script>
<template>
  <header class="page-head">
    <div>
      <span class="eyebrow">TRAO ĐỔI NỘI BỘ</span>
      <h1>Nhắn tin</h1>
      <p>Hội thoại riêng, nhóm, kênh phòng ban và trao đổi theo công việc, hồ sơ.</p>
    </div>
    <div class="page-actions">
      <button class="button" @click="showNew = true">
        <MessageSquarePlus :size="18" />Hội thoại mới
      </button>
    </div>
  </header>
  <section class="card chat-layout" :class="{ 'has-active': !!activeId }">
    <aside class="chat-list">
      <label class="search-box" style="margin: 14px; min-width: 0"
        ><Search :size="16" /><input
          v-model="filter"
          type="search"
          placeholder="Tìm hội thoại…"
          aria-label="Tìm hội thoại"
      /></label>
      <StatePanel
        :loading="list.isPending.value"
        :error="list.error.value"
        :empty="list.data.value?.items.length === 0"
        title="Chưa có hội thoại"
        description="Bắt đầu trò chuyện với đồng nghiệp hoặc mở trao đổi từ một công việc."
        @retry="list.refetch()"
      />
      <button
        v-for="item in visibleList"
        :key="item.id"
        class="chat-list-item"
        :class="{ active: item.id === activeId }"
        @click="activeId = item.id"
      >
        <span class="avatar">{{
          item.kind === 'direct' ? initials(item.title) : kindLabel[item.kind][0]
        }}</span>
        <span class="grow">
          <strong>{{ item.title }}</strong>
          <small>{{
            item.last_message
              ? `${item.last_message.mine ? 'Bạn' : item.last_message.sender_name}: ${item.last_message.deleted ? 'đã xóa tin nhắn' : item.last_message.body}`
              : kindLabel[item.kind]
          }}</small>
        </span>
        <span v-if="item.unread" class="unread-badge">{{ item.unread }}</span>
      </button>
    </aside>
    <div class="chat-pane">
      <template v-if="activeId && conversation.data.value">
        <header class="chat-header">
          <button class="icon-button chat-back" aria-label="Quay lại danh sách" @click="activeId = ''">
            <X :size="18" />
          </button>
          <div class="grow">
            <strong>{{ conversation.data.value.title }}</strong>
            <small class="muted"
              >{{ kindLabel[conversation.data.value.kind] }} ·
              {{ conversation.data.value.member_count }} thành viên</small
            >
          </div>
          <RouterLink
            v-if="conversation.data.value.ref_type"
            :to="`/${conversation.data.value.ref_type === 'task' ? 'tasks' : 'cases'}/${conversation.data.value.ref_id}`"
            class="button ghost small"
            >Mở {{ conversation.data.value.ref_type === 'task' ? 'công việc' : 'hồ sơ' }}</RouterLink
          >
          <button
            v-if="conversation.data.value.kind !== 'direct' && conversation.data.value.my_role === 'owner'"
            class="icon-button"
            aria-label="Thêm thành viên"
            title="Thêm thành viên"
            @click="showAdd = true"
          >
            <UserPlus :size="18" />
          </button>
          <button
            v-if="conversation.data.value.kind !== 'direct'"
            class="icon-button"
            aria-label="Rời hội thoại"
            title="Rời hội thoại"
            @click="leave"
          >
            <Users :size="18" />
          </button>
        </header>
        <div ref="scroller" class="chat-messages">
          <button v-if="hasMoreBefore" class="button ghost small load-older" @click="loadOlder">
            Tải tin nhắn cũ hơn
          </button>
          <p v-if="!messages.length && !latest.isPending.value" class="muted chat-empty">
            Chưa có tin nhắn. Hãy gửi lời chào đầu tiên.
          </p>
          <div
            v-for="message in messages"
            :key="message.id"
            class="chat-message"
            :class="{ mine: message.mine }"
          >
            <div class="bubble">
              <small v-if="!message.mine" class="sender">{{ message.sender_name }}</small>
              <div v-if="message.reply_to" class="reply-quote">
                <strong>{{ message.reply_to.sender_name }}</strong>
                {{ message.reply_to.body || 'Tin nhắn đã xóa' }}
              </div>
              <p v-if="message.deleted" class="muted"><em>Tin nhắn đã bị xóa</em></p>
              <p v-else class="prewrap">{{ message.body }}</p>
              <small class="meta"
                >{{ formatDate(message.created_at, true)
                }}<template v-if="message.edited_at"> · đã sửa</template></small
              >
              <div v-if="Object.keys(message.reactions).length" class="reactions">
                <button
                  v-for="(people, emoji) in message.reactions"
                  :key="emoji"
                  :class="{ mine: people.includes(session.user?.id ?? '') }"
                  @click="react(message, String(emoji))"
                >
                  {{ emoji }} {{ people.length }}
                </button>
              </div>
            </div>
            <div v-if="!message.deleted" class="message-tools">
              <button aria-label="Thả cảm xúc" title="Thả cảm xúc" @click="picker = picker === message.id ? null : message.id">
                <SmilePlus :size="15" /></button
              ><button aria-label="Trả lời" title="Trả lời" @click="replyTo = message">
                <Reply :size="15" /></button
              ><button aria-label="Tạo việc từ tin nhắn" title="Tạo việc" @click="taskFrom = message">
                <ListPlus :size="15" /></button
              ><template v-if="message.mine"
                ><button aria-label="Sửa" title="Sửa" @click="startEdit(message)">
                  <Pencil :size="15" /></button
                ><button aria-label="Xóa" title="Xóa" @click="remove(message)">
                  <Trash2 :size="15" /></button
              ></template>
              <div v-if="picker === message.id" class="emoji-picker">
                <button v-for="emoji in EMOJI" :key="emoji" @click="react(message, emoji)">
                  {{ emoji }}
                </button>
              </div>
            </div>
          </div>
        </div>
        <div v-if="error" class="notice error" style="margin: 0 16px">{{ errorText(error) }}</div>
        <div v-if="replyTo || editing" class="composer-context">
          <span v-if="editing">Đang sửa tin nhắn</span
          ><span v-else
            >Trả lời <strong>{{ replyTo?.sender_name }}</strong>: {{ replyTo?.body.slice(0, 80) }}</span
          ><button
            class="icon-button"
            aria-label="Bỏ"
            @click="
              () => {
                replyTo = null
                if (editing) draft = ''
                editing = null
              }
            "
          >
            <X :size="15" />
          </button>
        </div>
        <form class="composer" @submit.prevent="send">
          <div style="position: relative">
            <button
              type="button"
              class="icon-button"
              aria-label="Nhắc tên"
              title="Nhắc tên"
              :disabled="!members.length"
              @click="showMention = !showMention"
            >
              <AtSign :size="18" />
            </button>
            <div v-if="showMention" class="mention-menu">
              <button v-for="member in members" :key="member.user_id" type="button" @click="mention(member)">
                {{ member.display_name }}
              </button>
            </div>
          </div>
          <textarea
            v-model="draft"
            rows="1"
            placeholder="Nhập tin nhắn… (Enter để gửi, Shift+Enter xuống dòng)"
            aria-label="Nội dung tin nhắn"
            @keydown="onKey"
          /><button class="button" :disabled="sending || !draft.trim()" aria-label="Gửi">
            <SendHorizontal :size="17" />
          </button>
        </form>
      </template>
      <div v-else class="state-panel" style="height: 100%">
        <MessageSquarePlus :size="32" /><strong>Chọn một hội thoại</strong
        ><span>Hoặc tạo hội thoại mới để bắt đầu trao đổi.</span>
      </div>
    </div>
  </section>
  <ModalDialog v-if="showNew" title="Hội thoại mới" @close="showNew = false">
    <div v-if="error" class="notice error error-inline">{{ errorText(error) }}</div>
    <form class="stack" @submit.prevent="createConversation">
      <div class="tabs">
        <button
          v-for="kind in [
            { value: 'direct', label: 'Riêng' },
            { value: 'group', label: 'Nhóm' },
            { value: 'department', label: 'Kênh phòng ban' },
          ] as const"
          :key="kind.value"
          type="button"
          class="tab"
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
      <div v-if="newKind === 'direct'" class="field">
        <label for="conv-person">Người nhận</label
        ><select
          id="conv-person"
          required
          @change="newMembers = [($event.target as HTMLSelectElement).value]"
        >
          <option value="">Chọn đồng nghiệp</option>
          <option v-for="user in otherUsers" :key="user.id" :value="user.id">
            {{ user.display_name }}
          </option>
        </select>
      </div>
      <div v-else-if="newKind === 'group'" class="field">
        <label for="conv-members">Thành viên</label
        ><select id="conv-members" v-model="newMembers" multiple size="6">
          <option v-for="user in otherUsers" :key="user.id" :value="user.id">
            {{ user.display_name }}
          </option>
        </select>
        <small>Giữ Ctrl để chọn nhiều người. Có thể thêm người từ nhiều phòng ban.</small>
      </div>
      <div v-else class="field">
        <label for="conv-dept">Phòng ban</label
        ><select id="conv-dept" v-model="newDepartment" required>
          <option value="">Chọn phòng ban</option>
          <option v-for="dept in departments.data.value?.items" :key="dept.id" :value="dept.id">
            {{ dept.name }}
          </option>
        </select>
        <small>Chỉ lãnh đạo phòng hoặc quản trị được tạo kênh phòng ban.</small>
      </div>
      <div class="form-actions">
        <button type="button" class="button secondary" @click="showNew = false">Hủy</button
        ><button class="button">Tạo hội thoại</button>
      </div>
    </form>
  </ModalDialog>
  <ModalDialog v-if="showAdd" title="Thêm thành viên" @close="showAdd = false">
    <div v-if="error" class="notice error error-inline">{{ errorText(error) }}</div>
    <form class="stack" @submit.prevent="addMembers">
      <div class="field">
        <label for="add-members">Đồng nghiệp</label
        ><select id="add-members" v-model="addIds" multiple size="6" required>
          <option
            v-for="user in otherUsers.filter(
              (u) => !conversation.data.value?.members?.some((m) => m.user_id === u.id),
            )"
            :key="user.id"
            :value="user.id"
          >
            {{ user.display_name }}
          </option>
        </select>
      </div>
      <label class="checkbox-label"
        ><input v-model="addHistory" type="checkbox" />Cho xem toàn bộ lịch sử trước khi tham gia</label
      >
      <div class="form-actions">
        <button type="button" class="button secondary" @click="showAdd = false">Hủy</button
        ><button class="button" :disabled="!addIds.length">Thêm</button>
      </div>
    </form>
  </ModalDialog>
  <TaskCreateDialog
    v-if="taskFrom"
    heading="Tạo việc từ tin nhắn"
    :default-title="taskFrom.body.slice(0, 120)"
    :source="{ type: 'message', id: taskFrom.id, label: taskFrom.body.slice(0, 200) }"
    @close="taskFrom = null"
    @created="taskCreated"
  />
</template>
