<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { Bookmark, Loader2, Megaphone, Newspaper, PenLine, Sparkles, UserRound } from 'lucide-vue-next'
import { api } from '../api'
import { toast } from '../ui/toast'
import { useUnsavedGuard } from '../ui/unsaved'
import { useSession } from '../stores/session'
import { formatDate, queryString } from '@dx/web-shared/api.ts'
import type { Page } from '@dx/web-shared/api.ts'
import type { Post, PostComment } from '@dx/web-shared/types.ts'
import StatePanel from '@dx/web-shared/components/StatePanel.vue'
import PostCard from '../feed/PostCard.vue'
import PostComposer from '../feed/PostComposer.vue'
import { greeting, longDay, postedToday, relativeTime } from '../feed/text'
import { scrollBehavior } from '../ui/preferences'
import '../feed/feed.css'
import { confirmDialog } from '@dx/web-shared/confirm.ts'
import '../feed/feed-modern.css'

const queryClient = useQueryClient()
const session = useSession()
const route = useRoute()
type Filter = 'all' | 'official' | 'saved' | 'mine'
const FILTERS: { value: Filter; label: string; icon: typeof Newspaper }[] = [
  { value: 'all', label: 'Tất cả', icon: Newspaper },
  { value: 'official', label: 'Chính thức', icon: Megaphone },
  { value: 'saved', label: 'Đã lưu', icon: Bookmark },
  { value: 'mine', label: 'Bài của tôi', icon: UserRound },
]
const filter = ref<Filter>('all')
const cursor = ref<string | null>(null)
const posts = useQuery({
  queryKey: computed(() => ['posts', filter.value, cursor.value]),
  queryFn: () =>
    api.request<Page<Post>>(`/posts${queryString({ filter: filter.value, cursor: cursor.value })}`),
  refetchInterval: 30_000,
})
const announcements = useQuery({
  queryKey: ['posts', 'official', 'side'],
  queryFn: () => api.request<Page<Post>>('/posts?filter=official'),
  refetchInterval: 60_000,
})
const items = computed(() => posts.data.value?.items ?? [])
// The heading: a greeting for the reader and how lively the feed is today.
const firstName = computed(() => session.user?.display_name.trim().split(/\s+/).at(-1) ?? '')
const today = computed(() => postedToday(items.value.map((post) => post.created_at)))
const officialCount = computed(() => announcements.data.value?.items.length ?? 0)
function setFilter(value: Filter) {
  filter.value = value
  cursor.value = null
}

const body = ref('')
const composer = ref<InstanceType<typeof PostComposer>>()
useUnsavedGuard(() => !!body.value.trim() || !!composer.value?.hasMedia)
async function focusComposer() {
  await nextTick()
  composer.value?.focus()
}
onMounted(() => {
  if (route.query.compose) focusComposer()
})
watch(
  () => route.query.compose,
  (value) => {
    if (value) focusComposer()
  },
)

const busy = ref(false)
const publishing = ref(false)
async function act(work: () => Promise<unknown>, done?: string) {
  busy.value = true
  try {
    await work()
    await queryClient.invalidateQueries({ queryKey: ['posts'] })
    if (done) toast.success(done)
    return true
  } catch (cause) {
    toast.error(cause)
    return false
  } finally {
    busy.value = false
  }
}
async function publish(audience: 'organization' | 'department', official: boolean, attachmentIds: string[]) {
  if (publishing.value) return
  publishing.value = true
  const ok = await act(
    () =>
      api.request('/posts', {
        method: 'POST',
        body: JSON.stringify({ body: body.value, audience, official, attachment_ids: attachmentIds }),
      }),
    official ? 'Đã đăng thông báo chính thức' : 'Đã đăng bài',
  )
  publishing.value = false
  if (ok) {
    body.value = ''
    composer.value?.reset()
    if (filter.value !== 'all' && filter.value !== 'mine') setFilter('all')
  }
}
function react(post: Post, kind: string) {
  return act(() =>
    post.my_reaction === kind
      ? api.request(`/posts/${post.id}/reactions/me`, { method: 'DELETE' })
      : api.request(`/posts/${post.id}/reactions/me`, { method: 'PUT', body: JSON.stringify({ kind }) }),
  )
}
function toggleSave(post: Post) {
  return act(
    () => api.request(`/posts/${post.id}/save`, { method: post.saved ? 'DELETE' : 'PUT' }),
    post.saved ? 'Đã bỏ lưu bài' : 'Đã lưu bài — xem lại ở mục “Đã lưu”',
  )
}
function togglePin(post: Post) {
  return act(
    () =>
      api.request(`/posts/${post.id}/pin`, {
        method: 'POST',
        body: JSON.stringify({ pinned: !post.pinned_at }),
      }),
    post.pinned_at ? 'Đã bỏ ghim' : 'Đã ghim bài lên đầu bảng tin',
  )
}
async function remove(post: Post) {
  if (await confirmDialog({ message: 'Xóa bài viết này? Bình luận và cảm xúc cũng bị xóa.', confirmLabel: 'Xóa bài viết', danger: true }))
    return act(() => api.request(`/posts/${post.id}`, { method: 'DELETE' }), 'Đã xóa bài')
}

const comments = ref<Record<string, PostComment[]>>({})
async function loadComments(post: Post) {
  try {
    const page = await api.request<Page<PostComment>>(`/posts/${post.id}/comments`)
    comments.value = { ...comments.value, [post.id]: page.items }
  } catch (cause) {
    toast.error(cause)
  }
}
function toggleComments(post: Post) {
  if (comments.value[post.id]) {
    const next = { ...comments.value }
    delete next[post.id]
    comments.value = next
  } else void loadComments(post)
}
function comment(post: Post, text: string) {
  return act(async () => {
    await api.request(`/posts/${post.id}/comments`, { method: 'POST', body: JSON.stringify({ body: text }) })
    await loadComments(post)
  })
}
async function removeComment(post: Post, item: PostComment) {
  if (!(await confirmDialog({ message: 'Xóa bình luận này?', confirmLabel: 'Xóa bình luận', danger: true }))) return
  await act(async () => {
    await api.request(`/post-comments/${item.id}`, { method: 'DELETE' })
    await loadComments(post)
  })
}
function firstLine(text: string) {
  const line = text.split('\n').find((value) => value.trim()) ?? ''
  if (!line) return 'Ảnh/video'
  return line.length > 90 ? `${line.slice(0, 90)}…` : line
}
async function openAnnouncement(post: Post) {
  setFilter('official')
  await posts.refetch()
  await nextTick()
  document.getElementById(`post-${post.id}`)?.scrollIntoView({ behavior: scrollBehavior(), block: 'start' })
}
</script>
<template>
  <header class="page-head compact">
    <h1 class="sr-only">Bảng tin</h1>
  </header>
  <div class="feed-page">
    <div class="feed-main">
      <section class="feed-hero" aria-labelledby="feed-hero-title">
        <div class="feed-hero-text">
          <span class="feed-hero-day">{{ longDay() }}</span>
          <h2 id="feed-hero-title">{{ greeting() }}{{ firstName ? `, ${firstName}` : '' }}</h2>
          <p>Tin tức, thông báo và lời cảm ơn trong cơ quan.</p>
        </div>
        <ul class="feed-hero-stats">
          <li>
            <Sparkles :size="15" aria-hidden="true" /><template v-if="today"
              ><strong>{{ today }}</strong> bài mới hôm nay</template
            ><template v-else>Hôm nay chưa có bài mới</template>
          </li>
          <li v-if="officialCount">
            <Megaphone :size="15" aria-hidden="true" /><strong>{{ officialCount }}</strong> thông báo chính thức
          </li>
        </ul>
      </section>
      <PostComposer
        v-if="session.can('feed.post')"
        ref="composer"
        v-model="body"
        :busy="busy"
        :publishing="publishing"
        @publish="publish"
      />
      <nav class="feed-filters" aria-label="Lọc bài viết">
        <button
          v-for="item in FILTERS"
          :key="item.value"
          type="button"
          :class="{ active: filter === item.value }"
          :aria-pressed="filter === item.value"
          @click="setFilter(item.value)"
        >
          <component :is="item.icon" :size="15" aria-hidden="true" />{{ item.label }}
        </button>
      </nav>
      <section v-if="posts.isPending.value || posts.error.value || !items.length" class="card">
        <StatePanel
          :loading="posts.isPending.value"
          :error="posts.error.value"
          :empty="items.length === 0"
          :rows="3"
          :title="
            filter === 'saved'
              ? 'Bạn chưa lưu bài nào'
              : filter === 'mine'
                ? 'Bạn chưa đăng bài nào'
                : filter === 'official'
                  ? 'Chưa có thông báo chính thức'
                  : 'Bảng tin còn trống'
          "
          :description="
            filter === 'saved'
              ? 'Bấm “Lưu” dưới một bài để đọc lại sau.'
              : 'Chia sẻ tin tức, kế hoạch hay lời cảm ơn với đồng nghiệp. Bạn chọn bài hiện cho phòng hay cả cơ quan.'
          "
          @retry="posts.refetch()"
          ><button
            v-if="session.can('feed.post') && filter !== 'saved'"
            class="button small"
            type="button"
            @click="focusComposer"
          >
            <PenLine :size="15" />Viết bài
          </button></StatePanel
        >
      </section>
      <PostCard
        v-for="post in items"
        :id="`post-${post.id}`"
        :key="post.id"
        :post="post"
        :comments="comments[post.id]"
        :busy="busy"
        :send-comment="comment"
        @react="(kind) => react(post, kind)"
        @save="toggleSave(post)"
        @pin="togglePin(post)"
        @remove="remove(post)"
        @toggle-comments="toggleComments(post)"
        @remove-comment="(item) => removeComment(post, item)"
      />
      <div v-if="posts.data.value?.has_more || cursor" class="feed-pager">
        <button
          v-if="cursor"
          class="button secondary small"
          type="button"
          :disabled="posts.isFetching.value"
          @click="cursor = null"
        >
          Về bài mới nhất
        </button>
        <button
          v-if="posts.data.value?.has_more"
          class="button secondary small"
          type="button"
          :disabled="posts.isFetching.value"
          @click="cursor = posts.data.value?.next_cursor ?? null"
        >
          <Loader2 v-if="posts.isFetching.value && cursor" :size="14" class="spin" />{{
            posts.isFetching.value && cursor ? 'Đang tải…' : 'Xem bài cũ hơn'
          }}
        </button>
      </div>
    </div>
    <aside class="feed-side">
      <section class="card feed-side-card">
        <header><Megaphone :size="17" /><h2>Thông báo chính thức</h2></header>
        <StatePanel
          :loading="announcements.isPending.value"
          :error="announcements.error.value"
          :empty="!announcements.data.value?.items.length"
          :rows="2"
          compact
          title="Chưa có thông báo"
          description="Thông báo của lãnh đạo sẽ hiện ở đây."
          @retry="announcements.refetch()"
        />
        <button
          v-for="post in announcements.data.value?.items.slice(0, 4)"
          :key="post.id"
          type="button"
          class="feed-side-item"
          @click="openAnnouncement(post)"
        >
          <strong>{{ firstLine(post.body) }}</strong>
          <small
            >{{ post.author_name }} ·
            <time :datetime="post.created_at" :title="formatDate(post.created_at, true)">{{
              relativeTime(post.created_at)
            }}</time></small
          >
        </button>
      </section>
      <section class="card feed-side-card feed-tips">
        <header><PenLine :size="17" /><h2>Viết bài hay hơn</h2></header>
        <ul>
          <li>Viết ý chính ở câu đầu — mọi người đọc nó trước.</li>
          <li>Dán đường dẫn <code>https://…</code> để đồng nghiệp bấm mở ngay.</li>
          <li>Chọn <strong>Phòng của tôi</strong> khi tin chỉ liên quan đến phòng.</li>
          <li><kbd>Ctrl</kbd> + <kbd>Enter</kbd> để đăng nhanh.</li>
        </ul>
      </section>
    </aside>
  </div>
</template>
