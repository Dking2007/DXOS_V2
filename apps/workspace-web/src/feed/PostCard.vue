<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import {
  Bookmark,
  BookmarkCheck,
  Building2,
  ChevronDown,
  Globe2,
  Megaphone,
  MessageCircle,
  MoreHorizontal,
  Pin,
  PinOff,
  SendHorizontal,
  ThumbsUp,
  Trash2,
} from 'lucide-vue-next'
import type { Post, PostComment } from '@dx/web-shared/types.ts'
import { formatDate } from '@dx/web-shared/api.ts'
import { useSession } from '../stores/session'
import { useDismiss } from '../ui/popover'
import { avatarHue, initials, isLong, linkify, REACTIONS, relativeTime } from './text'
import MediaViewer from './MediaViewer.vue'
import PostMediaGrid from './PostMediaGrid.vue'


const props = defineProps<{ post: Post; comments?: PostComment[]; busy: boolean }>()
const emit = defineEmits<{
  react: [kind: string]
  save: []
  pin: []
  remove: []
  toggleComments: []
  comment: [text: string]
  removeComment: [item: PostComment]
}>()
const session = useSession()

const expanded = ref(false)
const viewing = ref<number | null>(null)
const long = computed(() => isLong(props.post.body))
const parts = computed(() => linkify(props.post.body))
const reactionTotal = computed(() => Object.values(props.post.reactions).reduce((sum, n) => sum + n, 0))
const topReactions = computed(() =>
  REACTIONS.filter((item) => props.post.reactions[item.kind])
    .sort((a, b) => props.post.reactions[b.kind] - props.post.reactions[a.kind])
    .slice(0, 3),
)
const reactionSummary = computed(() =>
  REACTIONS.filter((item) => props.post.reactions[item.kind])
    .map((item) => `${item.emoji} ${item.name}: ${props.post.reactions[item.kind]}`)
    .join(' · '),
)
const mine = computed(() => REACTIONS.find((item) => item.kind === props.post.my_reaction))

// Reaction picker: opens on hover (desktop) or the small arrow (touch, keyboard).
const picker = ref(false)
const pickerRoot = ref<HTMLElement>()
useDismiss(pickerRoot, picker)
let hoverTimer = 0
function hoverPicker(show: boolean) {
  window.clearTimeout(hoverTimer)
  hoverTimer = window.setTimeout(() => (picker.value = show), show ? 350 : 250)
}
function choose(kind: string) {
  picker.value = false
  emit('react', kind)
}

const menu = ref(false)
const menuRoot = ref<HTMLElement>()
useDismiss(menuRoot, menu)

const draft = ref('')
const commentInput = ref<HTMLInputElement>()
async function openComments() {
  if (!props.comments) emit('toggleComments')
  await nextTick()
  commentInput.value?.focus()
}
function sendComment() {
  const text = draft.value.trim()
  if (!text) return
  emit('comment', text)
  draft.value = ''
}
const me = computed(() => session.user?.display_name ?? '')
</script>
<template>
  <article class="card feed-post" :class="{ official: post.official, pinned: post.pinned_at }">
    <div v-if="post.official" class="feed-official-band"><Megaphone :size="14" />Thông báo chính thức</div>
    <header class="feed-post-head">
      <span class="feed-avatar" :style="{ '--hue': avatarHue(post.author_name) }" aria-hidden="true">{{
        initials(post.author_name)
      }}</span>
      <div class="grow">
        <strong>{{ post.author_name }}</strong>
        <small>
          <time :datetime="post.created_at" :title="formatDate(post.created_at, true)">{{
            relativeTime(post.created_at)
          }}</time>
          ·
          <span class="feed-scope"
            ><Globe2 v-if="post.audience === 'organization'" :size="12" /><Building2 v-else :size="12" />{{
              post.audience === 'organization' ? 'Toàn cơ quan' : post.department_name
            }}</span
          >
        </small>
      </div>
      <span v-if="post.pinned_at" class="feed-pin"><Pin :size="12" />Đã ghim</span>
      <div v-if="post.can_moderate || post.can_edit" ref="menuRoot" class="feed-menu">
        <button
          class="icon-button"
          type="button"
          aria-label="Thao tác khác"
          aria-haspopup="menu"
          :aria-expanded="menu"
          @click="menu = !menu"
        >
          <MoreHorizontal :size="18" />
        </button>
        <div v-if="menu" class="dropdown feed-menu-list" role="menu">
          <button v-if="post.can_moderate" type="button" role="menuitem" @click="(menu = false), emit('pin')">
            <PinOff v-if="post.pinned_at" :size="16" /><Pin v-else :size="16" />{{ post.pinned_at ? 'Bỏ ghim' : 'Ghim lên đầu' }}
          </button>
          <button type="button" role="menuitem" class="danger" @click="(menu = false), emit('remove')">
            <Trash2 :size="16" />Xóa bài
          </button>
        </div>
      </div>
    </header>
    <div v-if="post.body" class="feed-body" :class="{ clamped: long && !expanded }">
      <template v-for="(part, index) in parts" :key="index"
        ><a v-if="part.href" :href="part.href" target="_blank" rel="noopener noreferrer">{{ part.text }}</a
        ><template v-else>{{ part.text }}</template></template
      >
    </div>
    <button v-if="long" class="feed-more" type="button" @click="expanded = !expanded">
      {{ expanded ? 'Thu gọn' : 'Xem thêm' }}
    </button>
    <PostMediaGrid v-if="post.attachments?.length" :items="post.attachments" @open="(n) => (viewing = n)" />
    <MediaViewer
      v-if="viewing !== null && post.attachments?.length"
      :items="post.attachments"
      :start="viewing"
      :caption="`${post.author_name} · ${relativeTime(post.created_at)}`"
      @close="viewing = null"
    />
    <div v-if="reactionTotal || post.comment_count" class="feed-stats">
      <span v-if="reactionTotal" class="feed-reacted" :title="reactionSummary"
        ><span class="feed-emoji-stack"><i v-for="item in topReactions" :key="item.kind">{{ item.emoji }}</i></span
        >{{ reactionTotal }}</span
      >
      <button v-if="post.comment_count" type="button" class="feed-stat-link" @click="emit('toggleComments')">
        {{ post.comment_count }} bình luận
      </button>
    </div>
    <div class="feed-actions">
      <div ref="pickerRoot" class="feed-react" @mouseenter="hoverPicker(true)" @mouseleave="hoverPicker(false)">
        <button
          type="button"
          class="feed-action"
          :class="{ active: mine }"
          :aria-pressed="!!mine"
          :disabled="busy"
          @click="emit('react', mine ? mine.kind : 'like')"
        >
          <span v-if="mine" class="feed-action-emoji">{{ mine.emoji }}</span><ThumbsUp v-else :size="17" />{{
            mine ? mine.name : 'Thích'
          }}
        </button>
        <button
          type="button"
          class="feed-react-more"
          aria-label="Chọn cảm xúc khác"
          :aria-expanded="picker"
          @click="picker = !picker"
        >
          <ChevronDown :size="14" />
        </button>
        <Transition name="pop">
          <div v-if="picker" class="feed-picker" role="menu" aria-label="Cảm xúc">
            <button
              v-for="item in REACTIONS"
              :key="item.kind"
              type="button"
              role="menuitem"
              :class="{ active: post.my_reaction === item.kind }"
              :aria-label="item.name"
              :title="item.name"
              @click="choose(item.kind)"
            >
              {{ item.emoji }}
            </button>
          </div>
        </Transition>
      </div>
      <button type="button" class="feed-action" @click="openComments">
        <MessageCircle :size="17" />Bình luận
      </button>
      <button type="button" class="feed-action" :class="{ active: post.saved }" :aria-pressed="post.saved" @click="emit('save')">
        <BookmarkCheck v-if="post.saved" :size="17" /><Bookmark v-else :size="17" />{{ post.saved ? 'Đã lưu' : 'Lưu' }}
      </button>
    </div>
    <div v-if="comments" class="feed-comments">
      <div v-for="item in comments" :key="item.id" class="feed-comment">
        <span class="feed-avatar small" :style="{ '--hue': avatarHue(item.author_name) }" aria-hidden="true">{{
          initials(item.author_name)
        }}</span>
        <div class="feed-bubble">
          <strong>{{ item.author_name }}</strong>
          <p>
            <template v-for="(part, index) in linkify(item.body)" :key="index"
              ><a v-if="part.href" :href="part.href" target="_blank" rel="noopener noreferrer">{{ part.text }}</a
              ><template v-else>{{ part.text }}</template></template
            >
          </p>
        </div>
        <small class="feed-comment-meta">
          <time :datetime="item.created_at" :title="formatDate(item.created_at, true)">{{ relativeTime(item.created_at) }}</time>
          <button v-if="item.can_delete" type="button" class="link-button" @click="emit('removeComment', item)">Xóa</button>
        </small>
      </div>
      <form class="feed-comment-form" @submit.prevent="sendComment">
        <span class="feed-avatar small" :style="{ '--hue': avatarHue(me) }" aria-hidden="true">{{ initials(me) }}</span>
        <input ref="commentInput" v-model="draft" placeholder="Viết bình luận…" aria-label="Viết bình luận" maxlength="3000" />
        <button class="icon-button" type="submit" aria-label="Gửi bình luận" :disabled="busy || !draft.trim()">
          <SendHorizontal :size="17" />
        </button>
      </form>
    </div>
  </article>
</template>
