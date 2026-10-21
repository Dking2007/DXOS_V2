<script setup lang="ts">
import { computed, ref } from 'vue'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import {
  Bookmark,
  BookmarkCheck,
  Megaphone,
  MessageCircle,
  Pin,
  PinOff,
  SendHorizontal,
  Trash2,
} from 'lucide-vue-next'
import { api } from '../api'
import { useSession } from '../stores/session'
import { errorText, formatDate, queryString } from '@dx/web-shared/api.ts'
import type { Page } from '@dx/web-shared/api.ts'
import type { Post, PostComment } from '@dx/web-shared/types.ts'
import StatePanel from '@dx/web-shared/components/StatePanel.vue'
const queryClient = useQueryClient()
const session = useSession()
const filter = ref<'all' | 'official' | 'saved' | 'mine'>('all')
const cursor = ref<string | null>(null)
const posts = useQuery({
  queryKey: computed(() => ['posts', filter.value, cursor.value]),
  queryFn: () =>
    api.request<Page<Post>>(`/posts${queryString({ filter: filter.value, cursor: cursor.value })}`),
  refetchInterval: 30_000,
})
const REACTIONS = [
  { kind: 'like', label: '👍', name: 'Thích' },
  { kind: 'love', label: '❤️', name: 'Yêu thích' },
  { kind: 'celebrate', label: '🎉', name: 'Chúc mừng' },
  { kind: 'insightful', label: '💡', name: 'Hữu ích' },
  { kind: 'support', label: '🤝', name: 'Ủng hộ' },
]
const body = ref('')
const audience = ref<'organization' | 'department'>('organization')
const official = ref(false)
const error = ref<unknown>(null)
const busy = ref(false)
const canOfficial = computed(
  () => session.can('feed.moderate') || (session.can('feed.official') && audience.value === 'department'),
)
async function refresh() {
  await queryClient.invalidateQueries({ queryKey: ['posts'] })
}
async function act(work: () => Promise<unknown>) {
  error.value = null
  busy.value = true
  try {
    await work()
    await refresh()
  } catch (cause) {
    error.value = cause
  } finally {
    busy.value = false
  }
}
async function publish() {
  await act(async () => {
    await api.request('/posts', {
      method: 'POST',
      body: JSON.stringify({
        body: body.value,
        audience: audience.value,
        official: official.value && canOfficial.value,
      }),
    })
    body.value = ''
    official.value = false
  })
}
function react(post: Post, kind: string) {
  return act(() =>
    post.my_reaction === kind
      ? api.request(`/posts/${post.id}/reactions/me`, { method: 'DELETE' })
      : api.request(`/posts/${post.id}/reactions/me`, {
          method: 'PUT',
          body: JSON.stringify({ kind }),
        }),
  )
}
function toggleSave(post: Post) {
  return act(() => api.request(`/posts/${post.id}/save`, { method: post.saved ? 'DELETE' : 'PUT' }))
}
function togglePin(post: Post) {
  return act(() =>
    api.request(`/posts/${post.id}/pin`, {
      method: 'POST',
      body: JSON.stringify({ pinned: !post.pinned_at }),
    }),
  )
}
function remove(post: Post) {
  if (window.confirm('Xóa bài viết này?'))
    return act(() => api.request(`/posts/${post.id}`, { method: 'DELETE' }))
}
const openComments = ref<Record<string, PostComment[]>>({})
const commentDraft = ref<Record<string, string>>({})
async function loadComments(post: Post) {
  const page = await api.request<Page<PostComment>>(`/posts/${post.id}/comments`)
  openComments.value = { ...openComments.value, [post.id]: page.items }
}
function toggleComments(post: Post) {
  if (openComments.value[post.id]) {
    const next = { ...openComments.value }
    delete next[post.id]
    openComments.value = next
  } else void loadComments(post)
}
async function comment(post: Post) {
  const text = commentDraft.value[post.id]?.trim()
  if (!text) return
  await act(async () => {
    await api.request(`/posts/${post.id}/comments`, {
      method: 'POST',
      body: JSON.stringify({ body: text }),
    })
    commentDraft.value[post.id] = ''
    await loadComments(post)
  })
}
async function removeComment(post: Post, item: PostComment) {
  await act(async () => {
    await api.request(`/post-comments/${item.id}`, { method: 'DELETE' })
    await loadComments(post)
  })
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
      <span class="eyebrow">BẢNG TIN NỘI BỘ</span>
      <h1>Bảng tin</h1>
      <p>Thông báo chính thức, chia sẻ và tương tác trong tổ chức.</p>
    </div>
  </header>
  <div class="feed-layout">
    <div class="stack">
      <section v-if="session.can('feed.post')" class="card">
        <form class="card-body stack" @submit.prevent="publish">
          <textarea
            v-model="body"
            rows="3"
            maxlength="10000"
            placeholder="Bạn muốn chia sẻ điều gì với đồng nghiệp?"
            aria-label="Nội dung bài viết"
          />
          <div class="composer-row">
            <select v-model="audience" aria-label="Phạm vi" class="compact-select">
              <option value="organization">Toàn tổ chức</option>
              <option value="department" :disabled="!session.user?.department_id">
                Phòng của tôi
              </option>
            </select>
            <label v-if="session.can('feed.official')" class="checkbox-label" style="margin: 0"
              ><input v-model="official" type="checkbox" :disabled="!canOfficial" />Thông báo
              chính thức</label
            >
            <button class="button" :disabled="busy || !body.trim()" style="margin-left: auto">
              <SendHorizontal :size="16" />Đăng bài
            </button>
          </div>
          <small v-if="official && canOfficial" class="muted"
            >Thông báo chính thức gửi thông báo đến mọi người trong phạm vi đã chọn.</small
          >
        </form>
      </section>
      <div v-if="error" class="notice error">{{ errorText(error) }}</div>
      <div class="tabs">
        <button
          v-for="tab in [
            { value: 'all', label: 'Tất cả' },
            { value: 'official', label: 'Chính thức' },
            { value: 'saved', label: 'Đã lưu' },
            { value: 'mine', label: 'Bài của tôi' },
          ] as const"
          :key="tab.value"
          class="tab"
          :class="{ active: filter === tab.value }"
          @click="
            () => {
              filter = tab.value
              cursor = null
            }
          "
        >
          {{ tab.label }}
        </button>
      </div>
      <section v-if="posts.isPending.value || posts.error.value || !posts.data.value?.items.length" class="card">
        <StatePanel
          :loading="posts.isPending.value"
          :error="posts.error.value"
          :empty="posts.data.value?.items.length === 0"
          title="Chưa có bài viết"
          description="Bài viết bạn được phép xem sẽ xuất hiện tại đây."
          @retry="posts.refetch()"
        />
      </section>
      <article
        v-for="post in posts.data.value?.items"
        :key="post.id"
        class="card post-card"
        :class="{ official: post.official }"
      >
        <header class="post-head">
          <span class="avatar">{{ initials(post.author_name) }}</span>
          <div class="grow">
            <strong>{{ post.author_name }}</strong>
            <small class="muted"
              >{{ formatDate(post.created_at, true) }} ·
              {{ post.audience === 'organization' ? 'Toàn tổ chức' : post.department_name }}</small
            >
          </div>
          <span v-if="post.pinned_at" class="tag"><Pin :size="12" /> Đã ghim</span>
          <span v-if="post.official" class="tag official-tag"><Megaphone :size="12" /> Chính thức</span>
        </header>
        <p class="post-body prewrap">{{ post.body }}</p>
        <div class="post-actions">
          <div class="reaction-bar">
            <button
              v-for="reaction in REACTIONS"
              :key="reaction.kind"
              :class="{ active: post.my_reaction === reaction.kind }"
              :aria-label="reaction.name"
              :title="reaction.name"
              @click="react(post, reaction.kind)"
            >
              {{ reaction.label
              }}<span v-if="post.reactions[reaction.kind]">{{ post.reactions[reaction.kind] }}</span>
            </button>
          </div>
          <button class="button ghost small" @click="toggleComments(post)">
            <MessageCircle :size="15" />{{ post.comment_count }} bình luận
          </button>
          <button
            class="icon-button"
            :aria-label="post.saved ? 'Bỏ lưu' : 'Lưu bài'"
            :title="post.saved ? 'Bỏ lưu' : 'Lưu bài'"
            @click="toggleSave(post)"
          >
            <BookmarkCheck v-if="post.saved" :size="17" /><Bookmark v-else :size="17" />
          </button>
          <button
            v-if="post.can_moderate"
            class="icon-button"
            :aria-label="post.pinned_at ? 'Bỏ ghim' : 'Ghim'"
            :title="post.pinned_at ? 'Bỏ ghim' : 'Ghim'"
            @click="togglePin(post)"
          >
            <PinOff v-if="post.pinned_at" :size="17" /><Pin v-else :size="17" />
          </button>
          <button
            v-if="post.can_edit || post.can_moderate"
            class="icon-button"
            aria-label="Xóa bài"
            title="Xóa bài"
            @click="remove(post)"
          >
            <Trash2 :size="17" />
          </button>
        </div>
        <div v-if="openComments[post.id]" class="post-comments">
          <div v-for="item in openComments[post.id]" :key="item.id" class="comment">
            <span class="avatar">{{ initials(item.author_name) }}</span>
            <div class="grow">
              <strong>{{ item.author_name }}</strong>
              <small class="muted"> · {{ formatDate(item.created_at, true) }}</small>
              <p class="prewrap">{{ item.body }}</p>
            </div>
            <button
              v-if="item.can_delete"
              class="icon-button"
              aria-label="Xóa bình luận"
              @click="removeComment(post, item)"
            >
              <Trash2 :size="15" />
            </button>
          </div>
          <form class="comment-form" @submit.prevent="comment(post)">
            <input
              v-model="commentDraft[post.id]"
              placeholder="Viết bình luận…"
              aria-label="Bình luận"
              maxlength="3000"
            /><button class="button small" :disabled="busy">Gửi</button>
          </form>
        </div>
      </article>
      <div v-if="posts.data.value?.has_more || cursor" class="pagination">
        <button class="button secondary small" :disabled="!cursor" @click="cursor = null">
          Mới nhất</button
        ><button
          class="button secondary small"
          :disabled="!posts.data.value?.has_more"
          @click="cursor = posts.data.value?.next_cursor ?? null"
        >
          Cũ hơn
        </button>
      </div>
    </div>
  </div>
</template>
