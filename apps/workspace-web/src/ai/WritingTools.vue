<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { ref } from 'vue'
import { Sparkles, Undo2 } from 'lucide-vue-next'
import { api } from '../api'
import { toast } from '../ui/toast'

/** Rewrite, proofread or title a post. The previous text is kept one step back to undo. */
const text = defineModel<string>({ required: true })
const busy = ref<'' | 'rewrite' | 'proofread' | 'title'>('')
const previous = ref<string | null>(null)
const titles = ref<string[]>([])
async function run(action: 'rewrite' | 'proofread' | 'title') {
  if (text.value.trim().length < 3) return
  busy.value = action
  try {
    if (action === 'title') {
      titles.value = (
        await api.request<{ titles: string[] }>('/ai/write', { method: 'POST', body: JSON.stringify({ action, text: text.value }) })
      ).titles
    } else {
      const result = await api.request<{ text: string }>('/ai/write', {
        method: 'POST',
        body: JSON.stringify({ action, text: text.value }),
      })
      previous.value = text.value
      text.value = result.text
    }
  } catch (error) {
    toast.error(error)
  } finally {
    busy.value = ''
  }
}
function useTitle(title: string) {
  previous.value = text.value
  text.value = `${title}\n\n${text.value}`
  titles.value = []
}
function undo() {
  if (previous.value === null) return
  text.value = previous.value
  previous.value = null
}
</script>
<template>
  <div class="ai-chips" aria-label="AI hỗ trợ viết">
    <button type="button" class="button ghost small ai-action" :disabled="!!busy" @mousedown.prevent @click="run('rewrite')">
      <Sparkles :size="14" />{{ busy === 'rewrite' ? 'Đang viết…' : 'Viết gọn lại' }}
    </button>
    <button type="button" class="button ghost small ai-action" :disabled="!!busy" @mousedown.prevent @click="run('proofread')">
      {{ busy === 'proofread' ? 'Đang sửa…' : 'Sửa chính tả' }}
    </button>
    <button type="button" class="button ghost small ai-action" :disabled="!!busy" @mousedown.prevent @click="run('title')">
      {{ busy === 'title' ? 'Đang nghĩ…' : 'Gợi ý tiêu đề' }}
    </button>
    <button v-if="previous !== null" type="button" class="button ghost small" @mousedown.prevent @click="undo">
      <Undo2 :size="14" />Hoàn tác
    </button>
    <button
      v-for="title in titles"
      :key="title"
      type="button"
      class="tag"
      title="Chèn làm dòng đầu"
      @mousedown.prevent
      @click="useTitle(title)"
    >
      {{ title }}
    </button>
  </div>
</template>
