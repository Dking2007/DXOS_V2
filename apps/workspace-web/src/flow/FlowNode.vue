<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { computed, inject } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import type { NodeProps } from '@vue-flow/core'
import { AlertTriangle, Ban, Check, Clock3, Hourglass, Plus, X } from 'lucide-vue-next'
import { KINDS, OUTCOMES, branchLabel, outputs, summary, tone } from './nodes'
import type { FlowNodeData } from './nodes'
import { FLOW_CONTEXT } from './context'
const props = defineProps<NodeProps<FlowNodeData>>()
const context = inject(FLOW_CONTEXT)!
const meta = computed(() => KINDS[props.data.kind])
const text = computed(() =>
  summary(props.data, context.triggers.value, context.userName, context.forms?.value ?? []),
)
const exits = computed(() => outputs(props.data.kind, props.data.config))
/** Ports spread evenly down the right edge, so two or three branches never overlap. */
function top(index: number) {
  return `${((index + 1) / (exits.value.length + 1)) * 100}%`
}
const statusLabel: Record<string, string> = {
  succeeded: 'Đã xong',
  would_run: 'Sẽ chạy',
  failed: 'Lỗi',
  waiting: 'Đang chờ',
  queued: 'Đang gửi',
  unknown: 'Chưa rõ kết quả',
  cancelled: 'Đã dừng',
  skipped: 'Bỏ qua',
}
</script>
<template>
  <div
    class="flow-node"
    :class="[
      `kind-${data.kind}`,
      data.status ? `run-${data.status}` : '',
      {
        selected,
        invalid: data.errors?.length,
        dimmed: context.overlay.value && !data.status,
        terminal: meta.terminal,
        branched: exits.length > 2,
      },
    ]"
    :style="{ '--node-color': meta.color }"
    :title="data.errors?.join('\n') || data.message || ''"
  >
    <Handle v-if="data.kind !== 'trigger'" type="target" :position="Position.Left" class="flow-handle" />
    <span class="flow-node-icon"><component :is="meta.icon" :size="22" :stroke-width="1.9" /></span>
    <div class="flow-node-text">
      <small>{{ meta.group === 'Kích hoạt' ? 'KÍCH HOẠT' : meta.title.toUpperCase() }}</small>
      <strong>{{ data.label || meta.title }}</strong>
      <span>{{ text }}</span>
      <em v-if="data.outcome" class="flow-node-outcome">→ {{ OUTCOMES[data.outcome] ?? data.outcome }}</em>
    </div>
    <span v-if="data.errors?.length" class="flow-node-flag error" aria-label="Cấu hình chưa hợp lệ"
      ><AlertTriangle :size="13"
    /></span>
    <span
      v-else-if="data.status"
      class="flow-node-flag"
      :class="data.status"
      :aria-label="statusLabel[data.status] ?? data.status"
      :title="statusLabel[data.status] ?? data.status"
    >
      <Check v-if="data.status === 'succeeded' || data.status === 'would_run'" :size="13" />
      <X v-else-if="data.status === 'failed'" :size="13" />
      <Hourglass v-else-if="data.status === 'waiting'" :size="13" />
      <Ban v-else-if="data.status === 'cancelled' || data.status === 'skipped'" :size="13" />
      <Clock3 v-else :size="13" />
    </span>
    <template v-if="exits.length">
      <template v-for="(exit, index) in exits" :key="exit">
        <Handle
          :id="exit"
          type="source"
          :position="Position.Right"
          class="flow-handle"
          :class="`handle-${tone(exit)}`"
          :style="{ top: top(index) }"
        />
        <span
          class="branch-tag"
          :class="[`tag-${tone(exit)}`, { taken: data.branch === exit }]"
          :style="{ top: `calc(${top(index)} - 9px)` }"
          >{{ branchLabel(data.kind, exit, data.config) }}</span
        >
      </template>
    </template>
    <template v-else-if="!meta.terminal">
      <Handle type="source" :position="Position.Right" class="flow-handle" />
      <button
        v-if="!context.readonly"
        class="flow-node-add nodrag"
        type="button"
        aria-label="Thêm bước sau"
        title="Thêm bước sau"
        @click.stop="context.addAfter(id)"
      >
        <Plus :size="13" />
      </button>
    </template>
  </div>
</template>
