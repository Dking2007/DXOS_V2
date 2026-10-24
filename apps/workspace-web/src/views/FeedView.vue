<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { Bookmark, Megaphone, Newspaper, PenLine, UserRound } from 'lucide-vue-next'
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
import { relativeTime } from '../feed/text'
import '../feed/feed.css'

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
  const ok = await act(
    () =>
      api.request('/posts', {
        method: 'POST',
        body: JSON.stringify({ body: body.value, audience, official, attachment_ids: attachmentIds }),
      }),
    official ? 'Đã đăng thông báo chính thức' : 'Đã đăng bài',
  )
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
function remove(post: Post) {
  if (window.confirm('Xóa bài viết này? Bình luận và cảm xúc cũng bị xóa.'))
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
async function comment(post: Post, text: string) {
  await act(async () => {
    await api.request(`/posts/${post.id}/comments`, { method: 'POST', body: JSON.stringify({ body: text }) })
    await loadComments(post)
  })
}
async function removeComment(post: Post, item: PostComment) {
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
  document.getElementById(`post-${post.id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}
</script>
<template>
  <header class="page-head">
    <div>
      <span class="eyebrow">BẢNG TIN NỘI BỘ</span>
      <h1>Bảng tin</h1>
      <p>Thông báo chính thức, tin tức và lời chia sẻ trong cơ quan.</p>
    </div>
  </header>
  <div class="feed-page">
    <div class="feed-main">
      <PostComposer v-if="session.can('feed.post')" ref="composer" v-model="body" :busy="busy" @publish="publish" />
      <nav class="feed-filters" aria-label="Lọc bài viết">
        <button
          v-for="item in FILTERS"
          :key="item.value"
          type="button"
          :class="{ active: filter === item.value }"
          :aria-pressed="filter === item.value"
          @click="setFilter(item.value)"
        >
          <component :is="item.icon" :size="15" />{{ item.label }}
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
        @react="(kind) => react(post, kind)"
        @save="toggleSave(post)"
        @pin="togglePin(post)"
        @remove="remove(post)"
        @toggle-comments="toggleComments(post)"
        @comment="(text) => comment(post, text)"
        @remove-comment="(item) => removeComment(post, item)"
      />
      <div v-if="posts.data.value?.has_more || cursor" class="feed-pager">
        <button v-if="cursor" class="button secondary small" type="button" @click="cursor = null">Về bài mới nhất</button>
        <button
          v-if="posts.data.value?.has_more"
          class="button secondary small"
          type="button"
          @click="cursor = posts.data.value?.next_cursor ?? null"
        >
          Xem bài cũ hơn
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
