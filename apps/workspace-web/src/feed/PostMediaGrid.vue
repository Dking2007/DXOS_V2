<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { computed } from 'vue'
import { Play } from 'lucide-vue-next'
import type { PostMedia } from '@dx/web-shared/types.ts'
import { gridLayout } from './media'

const props = defineProps<{ items: PostMedia[] }>()
const emit = defineEmits<{ open: [index: number] }>()
const grid = computed(() => gridLayout(props.items.length))
// A post with one video plays it in place; anything else opens the viewer.
const singleVideo = computed(() => props.items.length === 1 && props.items[0].kind === 'video')
</script>
<template>
  <div v-if="singleVideo" class="feed-media single-video">
    <video :src="items[0].url" controls preload="metadata" playsinline />
  </div>
  <div v-else class="feed-media" :class="grid.layout">
    <button
      v-for="(item, index) in items.slice(0, grid.shown)"
      :key="item.id"
      type="button"
      class="feed-tile"
      :aria-label="item.kind === 'video' ? `Xem video ${item.name}` : `Xem ảnh ${item.name}`"
      @click="emit('open', index)"
    >
      <img v-if="item.kind === 'image'" :src="item.url" :alt="item.alt || item.name" loading="lazy" />
      <template v-else>
        <video :src="`${item.url}#t=0.1`" preload="metadata" muted playsinline tabindex="-1" />
        <span class="feed-play" aria-hidden="true"><Play :size="26" fill="currentColor" /></span>
      </template>
      <span v-if="index === grid.shown - 1 && grid.more" class="feed-tile-more">+{{ grid.more }}</span>
    </button>
  </div>
</template>
