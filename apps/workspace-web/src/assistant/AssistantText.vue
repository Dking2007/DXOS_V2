<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { computed, h, type VNode } from 'vue'
import { parseMarkdown, type Inline } from './markdown'

const props = defineProps<{ text: string }>()
const blocks = computed(() => parseMarkdown(props.text))

function inline(parts: Inline[]): (VNode | string)[] {
  return parts.map((part) => {
    if (part.t === 'bold') return h('strong', part.v)
    if (part.t === 'code') return h('code', part.v)
    if (part.t === 'cite') return h('sup', { class: 'assistant-cite' }, `[${part.n}]`)
    if (part.t === 'link') return h('a', { href: part.href, target: '_blank', rel: 'noopener noreferrer' }, part.v)
    return part.v
  })
}
const Render = () =>
  blocks.value.map((block) => {
    if (block.t === 'h') return h('p', { class: 'assistant-heading' }, inline(block.inline))
    if (block.t === 'code') return h('pre', h('code', block.v))
    if (block.t === 'p') return h('p', inline(block.inline))
    return h(
      block.t,
      block.items.map((item) => h('li', inline(item))),
    )
  })
</script>
<template>
  <div class="assistant-text"><Render /></div>
</template>
