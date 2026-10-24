<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { AlertCircle, Building2, Globe2, ImagePlus, Megaphone, Play, SendHorizontal, X } from 'lucide-vue-next'
import { useSession } from '../stores/session'
import { toast } from '../ui/toast'
import { MAX_MEDIA, MEDIA_ACCEPT, useMediaUploads } from './media'
import { avatarHue, initials } from './text'

const body = defineModel<string>({ required: true })
const props = defineProps<{ busy: boolean }>()
const emit = defineEmits<{
  publish: [audience: 'organization' | 'department', official: boolean, attachmentIds: string[]]
}>()
const session = useSession()
const audience = ref<'organization' | 'department'>('organization')
const official = ref(false)
const focused = ref(false)
const dragging = ref(false)
const textarea = ref<HTMLTextAreaElement>()
const picker = ref<HTMLInputElement>()
const LIMIT = 10_000
const media = useMediaUploads(() => session.user?.csrf_token ?? '')
const name = computed(() => session.user?.display_name ?? '')
const firstName = computed(() => name.value.split(' ').slice(-1)[0] ?? '')
const open = computed(() => focused.value || !!body.value || media.items.value.length > 0)
// Department managers may announce to their own department; moderators to everyone.
const canOfficial = computed(
  () => session.can('feed.moderate') || (session.can('feed.official') && audience.value === 'department'),
)
const ready = computed(
  () =>
    (!!body.value.trim() || media.ids.value.length > 0) &&
    !media.uploading.value &&
    !media.failed.value &&
    !props.busy,
)
const status = computed(() => {
  if (media.uploading.value) return 'Đang tải ảnh/video lên…'
  if (media.failed.value) return 'Có tệp tải lên lỗi — bỏ tệp đó để đăng.'
  return ''
})

function grow() {
  const element = textarea.value
  if (!element) return
  element.style.height = 'auto'
  element.style.height = `${Math.min(element.scrollHeight, 420)}px`
}
function addFiles(files: Iterable<File>) {
  const rejected = media.add(files)
  for (const message of rejected) toast.error(message)
}
function onPick(event: Event) {
  const input = event.target as HTMLInputElement
  addFiles(input.files ?? [])
  input.value = ''
}
function onDrop(event: DragEvent) {
  dragging.value = false
  addFiles(event.dataTransfer?.files ?? [])
}
function onPaste(event: ClipboardEvent) {
  const files = [...(event.clipboardData?.files ?? [])]
  if (!files.length) return
  event.preventDefault()
  addFiles(files)
}
function submit() {
  if (!ready.value) return
  emit('publish', audience.value, official.value && canOfficial.value, media.ids.value)
}
function reset() {
  official.value = false
  media.clear()
  void nextTick(grow)
}
function focus() {
  textarea.value?.scrollIntoView({ block: 'center' })
  textarea.value?.focus()
}
const hasMedia = computed(() => media.items.value.length > 0)
defineExpose({ focus, reset, hasMedia })
</script>
<template>
  <form
    class="card feed-composer"
    :class="{ open, dragging }"
    @submit.prevent="submit"
    @dragover.prevent="dragging = true"
    @dragleave.self="dragging = false"
    @drop.prevent="onDrop"
  >
    <div class="feed-composer-main">
      <span class="feed-avatar" :style="{ '--hue': avatarHue(name) }" aria-hidden="true">{{ initials(name) }}</span>
      <textarea
        ref="textarea"
        v-model="body"
        rows="1"
        :maxlength="LIMIT"
        :placeholder="`Chia sẻ điều gì đó với đồng nghiệp, ${firstName}…`"
        aria-label="Nội dung bài viết"
        @input="grow"
        @focus="focused = true"
        @blur="focused = false"
        @paste="onPaste"
        @keydown.ctrl.enter.prevent="submit"
        @keydown.meta.enter.prevent="submit"
      />
      <button
        type="button"
        class="feed-media-button"
        :disabled="media.items.value.length >= MAX_MEDIA"
        title="Thêm ảnh hoặc video (có thể kéo thả hoặc dán)"
        @mousedown.prevent
        @click="picker?.click()"
      >
        <ImagePlus :size="20" /><span>Ảnh/Video</span>
      </button>
      <input ref="picker" type="file" multiple :accept="MEDIA_ACCEPT" hidden @change="onPick" />
    </div>
    <div v-if="media.items.value.length" class="feed-pending" aria-label="Ảnh và video sẽ đăng">
      <div
        v-for="item in media.items.value"
        :key="item.key"
        class="feed-pending-item"
        :class="{ failed: item.error, done: item.media }"
        :title="item.error || item.file.name"
      >
        <img v-if="item.kind === 'image'" :src="item.preview" :alt="item.file.name" />
        <template v-else>
          <video :src="item.preview" muted preload="metadata" />
          <span class="feed-pending-play" aria-hidden="true"><Play :size="16" fill="currentColor" /></span>
        </template>
        <span v-if="!item.media && !item.error" class="feed-pending-progress" role="progressbar" :aria-valuenow="Math.round(item.progress * 100)" aria-valuemin="0" aria-valuemax="100"
          ><i :style="{ width: `${Math.round(item.progress * 100)}%` }"
        /></span>
        <span v-if="item.error" class="feed-pending-error"><AlertCircle :size="18" /></span>
        <button type="button" class="feed-pending-remove" :aria-label="`Bỏ ${item.file.name}`" @mousedown.prevent @click="media.remove(item.key)">
          <X :size="13" />
        </button>
      </div>
    </div>
    <p v-if="status" class="feed-pending-status" :class="{ error: media.failed.value }" role="status">{{ status }}</p>
    <div v-if="dragging" class="feed-drop-hint" aria-hidden="true"><ImagePlus :size="22" />Thả ảnh hoặc video vào đây</div>
    <div v-if="open" class="feed-composer-tools">
      <div class="feed-audience" role="radiogroup" aria-label="Ai thấy bài viết">
        <button
          type="button"
          role="radio"
          :aria-checked="audience === 'organization'"
          :class="{ active: audience === 'organization' }"
          @mousedown.prevent
          @click="audience = 'organization'"
        >
          <Globe2 :size="15" />Toàn cơ quan
        </button>
        <button
          type="button"
          role="radio"
          :aria-checked="audience === 'department'"
          :class="{ active: audience === 'department' }"
          :disabled="!session.user?.department_id"
          @mousedown.prevent
          @click="audience = 'department'"
        >
          <Building2 :size="15" />Phòng của tôi
        </button>
      </div>
      <label
        v-if="session.can('feed.official')"
        class="feed-official-toggle"
        :class="{ on: official && canOfficial, disabled: !canOfficial }"
        :title="canOfficial ? 'Gửi thông báo đến mọi người trong phạm vi' : 'Chỉ đăng thông báo chính thức cho phòng của bạn'"
        @mousedown.prevent
      >
        <input v-model="official" type="checkbox" :disabled="!canOfficial" /><Megaphone :size="15" />Thông báo chính thức
      </label>
      <span class="grow" />
      <small v-if="body.length > LIMIT * 0.9" class="feed-counter">{{ body.length.toLocaleString('vi-VN') }}/{{ LIMIT.toLocaleString('vi-VN') }}</small>
      <button class="button" :disabled="!ready" title="Ctrl + Enter để đăng nhanh" @mousedown.prevent>
        <SendHorizontal :size="16" />{{ busy ? 'Đang đăng…' : 'Đăng bài' }}
      </button>
    </div>
    <p v-if="official && canOfficial" class="feed-official-note">
      <Megaphone :size="14" />Mọi người trong phạm vi sẽ nhận thông báo về bài này.
    </p>
  </form>
</template>
