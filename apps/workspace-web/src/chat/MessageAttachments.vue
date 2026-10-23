<script setup lang="ts">
import { computed } from 'vue'
import { Download, FileArchive, FileSpreadsheet, FileText, FileType2, Presentation } from 'lucide-vue-next'
import type { ChatAttachment } from '@dx/web-shared/types.ts'
import { fileSize } from './upload'
const props = defineProps<{ items: ChatAttachment[]; mine: boolean }>()
const emit = defineEmits<{ open: [item: ChatAttachment] }>()
const images = computed(() => props.items.filter((i) => i.kind === 'image'))
const media = computed(() => props.items.filter((i) => i.kind === 'video' || i.kind === 'audio'))
const files = computed(() => props.items.filter((i) => i.kind === 'file'))
function icon(item: ChatAttachment) {
  const ext = item.name.split('.').pop()?.toLowerCase() ?? ''
  if (['xlsx', 'csv'].includes(ext)) return FileSpreadsheet
  if (ext === 'pptx') return Presentation
  if (ext === 'zip') return FileArchive
  if (ext === 'pdf') return FileType2
  return FileText
}
function tone(item: ChatAttachment) {
  const ext = item.name.split('.').pop()?.toLowerCase() ?? ''
  if (['xlsx', 'csv'].includes(ext)) return 'green'
  if (ext === 'pptx') return 'orange'
  if (ext === 'pdf') return 'red'
  if (ext === 'zip') return 'purple'
  return 'blue'
}
</script>
<template>
  <div class="chat-attachments" :class="{ mine }">
    <div v-if="images.length" class="chat-images" :class="`count-${Math.min(images.length, 4)}`">
      <button
        v-for="(item, index) in images.slice(0, 4)"
        :key="item.id"
        type="button"
        class="chat-image"
        :aria-label="`Xem ảnh ${item.name}`"
        @click="emit('open', item)"
      >
        <img :src="item.url" :alt="item.name" loading="lazy" />
        <span v-if="index === 3 && images.length > 4" class="chat-image-more">+{{ images.length - 4 }}</span>
      </button>
    </div>
    <template v-for="item in media" :key="item.id">
      <video v-if="item.kind === 'video'" class="chat-video" :src="item.url" controls preload="metadata" />
      <audio v-else class="chat-audio" :src="item.url" controls preload="none" />
    </template>
    <a
      v-for="item in files"
      :key="item.id"
      class="chat-file"
      :href="`${item.url}?download=1`"
      :download="item.name"
      :title="`Tải ${item.name}`"
    >
      <span class="chat-file-icon" :class="tone(item)"><component :is="icon(item)" :size="20" /></span>
      <span class="grow"><strong>{{ item.name }}</strong><small>{{ fileSize(item.size) }}</small></span>
      <Download :size="16" />
    </a>
  </div>
</template>
