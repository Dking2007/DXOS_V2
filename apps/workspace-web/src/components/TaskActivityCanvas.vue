<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<!-- A task's history drawn on a read-only workflow canvas, in the same style as the process designer.
     `down` fits the narrow side card (no pan or zoom, the page scrolls as usual); `right` is the wide
     view: main steps left to right, wrapping to as many rows as the width needs, side notes hanging
     below, with pan/zoom controls. -->
<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { BaseEdge, Handle, MarkerType, Position, VueFlow, useVueFlow } from '@vue-flow/core'
import type { Edge, Node } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/controls/dist/style.css'
import { formatDate } from '@dx/web-shared/api.ts'
import { canvasLayout, stepsPerRow } from '../ui/taskActivity'
import type { ActivityStep, CanvasDirection, PlacedStep } from '../ui/taskActivity'
import { activityIcon } from './taskActivityIcons'

const props = defineProps<{
  steps: ActivityStep[]
  direction: CanvasDirection
  /** The newest step of the whole history (it may be outside `steps` when older ones are folded). */
  latestId?: string
  flowId: string
}>()

const wide = computed(() => props.direction === 'right')
// The wide view wraps its main line to the width it is given, so it is measured first.
const box = ref<HTMLElement | null>(null)
const width = ref(0)
let observer: ResizeObserver | undefined
onMounted(() => {
  if (!box.value) return
  width.value = box.value.clientWidth
  observer = new ResizeObserver(([entry]) => (width.value = entry.contentRect.width))
  observer.observe(box.value)
})
onBeforeUnmount(() => observer?.disconnect())
const perRow = computed(() => (wide.value && width.value ? stepsPerRow(width.value) : Infinity))
const layout = computed(() => canvasLayout(props.steps, props.direction, props.latestId, perRow.value))

const nodes = computed<Node<PlacedStep>[]>(() =>
  layout.value.placed.map((placed) => ({
    id: placed.step.id,
    type: 'activity',
    position: { x: placed.x, y: placed.y },
    data: placed,
    draggable: false,
    selectable: false,
    connectable: false,
    style: { width: `${placed.width}px`, height: `${placed.height}px` },
  })),
)
const edges = computed<Edge[]>(() =>
  layout.value.links.map((link) => {
    const sideways = wide.value && !link.aside
    return {
      id: link.id,
      source: link.source,
      target: link.target,
      sourceHandle: sideways ? 'r' : 'b',
      targetHandle: sideways ? 'l' : 't',
      type: link.corridor === undefined ? 'smoothstep' : 'wrap',
      data: { corridor: link.corridor },
      markerEnd: MarkerType.ArrowClosed,
      class: ['activity-edge', `edge-${link.tone}`, { aside: link.aside }],
      selectable: false,
      focusable: false,
    }
  }),
)

/** Day and time; the year only when it is not this year, so the line fits the node. */
const thisYear = String(new Date().getFullYear())
function when(at: string) {
  return formatDate(at, true).replace(`/${thisYear}`, '').replace(`${thisYear}-`, '')
}

/** Back to the start of the next row: right, down to the gap between the rows, left, down into it. */
function wrapPath(sx: number, sy: number, tx: number, ty: number, corridor: number) {
  const out = sx + 20
  const into = tx - 20
  return `M ${sx} ${sy} H ${out} V ${corridor} H ${into} V ${ty} H ${tx}`
}

// Fit the wide view once it is laid out, and again when the dialog is resized and the rows rewrap.
const flow = useVueFlow(props.flowId)
function fit() {
  if (!wide.value) return
  requestAnimationFrame(() => void flow.fitView({ padding: 0.06, maxZoom: 1 }))
}
flow.onNodesInitialized(fit)
watch(perRow, () => nextTick(fit))

const bottom = computed(() => Math.max(0, ...layout.value.placed.map((p) => p.y + p.height)))
/** The card shows every step at full size, so its height follows them; the wide view up to 70% of the window. */
const height = computed(() =>
  wide.value
    ? `clamp(240px, ${Math.ceil(bottom.value) + 64}px, 70vh)`
    : `${Math.ceil(bottom.value * 1.14) + 12}px`,
)
</script>
<template>
  <div ref="box" class="activity-canvas" :class="{ wide }" :style="{ height }" aria-hidden="true">
    <VueFlow
      v-if="!wide || width"
      :id="flowId"
      :nodes="nodes"
      :edges="edges"
      :nodes-draggable="false"
      :nodes-connectable="false"
      :elements-selectable="false"
      :pan-on-drag="wide"
      :zoom-on-scroll="wide"
      :zoom-on-pinch="wide"
      :zoom-on-double-click="false"
      :prevent-scrolling="wide"
      :min-zoom="wide ? 0.3 : 0.5"
      :max-zoom="wide ? 1.6 : 1"
      :fit-view-on-init="!wide"
      :fit-view-params="{ padding: 0.06, maxZoom: 1 }"
    >
      <template #node-activity="{ data }">
        <div
          class="activity-node"
          :class="[`tone-${data.step.tone}`, { minor: !data.step.major, latest: data.latest }]"
          :title="[data.step.label, data.step.note, data.step.reason].filter(Boolean).join('\n')"
        >
          <Handle id="t" type="target" :position="Position.Top" class="activity-handle" />
          <Handle id="l" type="target" :position="Position.Left" class="activity-handle" />
          <span v-if="data.latest" class="activity-node-now">Mới nhất</span>
          <span class="activity-node-icon">
            <component :is="activityIcon(data.step.action)" :size="data.step.major ? 17 : 13" />
          </span>
          <div class="activity-node-text">
            <strong
              >{{ data.step.label
              }}<span v-if="!data.step.major && data.step.note" class="activity-node-inline">{{
                data.step.note
              }}</span></strong
            >
            <small class="activity-node-meta"
              ><span class="activity-node-actor">{{ data.step.actor || 'Hệ thống' }}</span
              ><span class="activity-node-time">· {{ when(data.step.at) }}</span></small
            >
            <small v-if="data.step.major && data.step.note" class="activity-node-note">{{ data.step.note }}</small>
            <q v-if="data.step.reason" class="activity-node-reason">{{ data.step.reason }}</q>
          </div>
          <Handle id="b" type="source" :position="Position.Bottom" class="activity-handle" />
          <Handle id="r" type="source" :position="Position.Right" class="activity-handle" />
        </div>
      </template>
      <template #edge-wrap="edge">
        <BaseEdge
          :id="edge.id"
          :path="wrapPath(edge.sourceX, edge.sourceY, edge.targetX, edge.targetY, edge.data.corridor)"
          :marker-end="edge.markerEnd"
        />
      </template>
      <Background :gap="18" :size="1.2" />
      <Controls v-if="wide" :show-interactive="false" position="bottom-right" />
    </VueFlow>
  </div>
</template>
<style scoped>
.activity-canvas {
  position: relative;
  min-height: 120px;
  background: var(--surface-2);
}
.activity-canvas.wide {
  border: 1px solid var(--border);
  border-radius: 10px;
  overflow: hidden;
}
.activity-canvas :deep(.vue-flow__background circle) {
  fill: var(--border-strong, var(--border));
}
.activity-canvas :deep(.vue-flow__node-activity) {
  padding: 0;
  border: 0;
  background: none;
  cursor: default;
}
.activity-handle {
  opacity: 0;
  pointer-events: none;
  min-width: 1px;
  min-height: 1px;
  width: 1px;
  height: 1px;
  border: 0;
}
/* Nodes: the same card-with-icon look as the process designer. */
.activity-node {
  position: relative;
  display: flex;
  gap: 10px;
  align-items: flex-start;
  box-sizing: border-box;
  width: 100%;
  height: 100%;
  padding: 9px 11px;
  border: 1px solid var(--border);
  border-left: 4px solid var(--tone-line);
  border-radius: 10px;
  background: var(--surface);
  color: var(--text);
  box-shadow: 0 1px 2px rgb(16 40 64 / 0.06);
  text-align: left;
}
.activity-node.minor {
  align-items: center;
  padding: 6px 10px;
  border-left-width: 1px;
  border-style: dashed;
  background: color-mix(in srgb, var(--surface) 70%, var(--surface-2));
}
.activity-node.latest {
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--tone-line) 45%, transparent);
}
.activity-node-icon {
  display: grid;
  flex: none;
  place-items: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: var(--tone-soft);
  color: var(--tone-ink);
}
.minor .activity-node-icon {
  width: 24px;
  height: 24px;
  border-radius: 6px;
}
.activity-node-text {
  display: grid;
  gap: 1px;
  min-width: 0;
}
.activity-node-text strong {
  display: flex;
  align-items: center;
  gap: 6px;
  overflow: hidden;
  font-size: 0.875rem;
  font-weight: 600;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.minor .activity-node-text strong {
  color: var(--muted);
  font-size: 0.8125rem;
  font-weight: 500;
}
.activity-node-now {
  position: absolute;
  top: -9px;
  right: 10px;
  padding: 0 7px;
  border: 1px solid var(--tone-line);
  border-radius: 999px;
  background: var(--tone-soft);
  color: var(--tone-ink);
  font-size: 0.6875rem;
  font-weight: 600;
}
.activity-node-meta,
.activity-node-note {
  overflow: hidden;
  color: var(--muted);
  font-size: 0.75rem;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.activity-node-note {
  color: var(--text);
}
/* A long name gives way; the time always shows. */
.activity-node-meta {
  display: flex;
  gap: 4px;
}
.activity-node-actor {
  overflow: hidden;
  text-overflow: ellipsis;
}
.activity-node-time {
  flex: none;
}
.activity-node-inline {
  overflow: hidden;
  color: var(--text);
  text-overflow: ellipsis;
}
.activity-node-inline::before {
  content: '· ';
  color: var(--muted);
}
.activity-node-reason {
  display: -webkit-box;
  margin-top: 3px;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  font-size: 0.75rem;
  font-style: italic;
  line-height: 1.35;
  overflow-wrap: anywhere;
}
/* Edges take the colour of the step they lead to; side notes hang on a dashed line. */
.activity-canvas :deep(.activity-edge path.vue-flow__edge-path) {
  stroke: color-mix(in srgb, var(--tone-ink) 55%, transparent);
  stroke-width: 2;
}
.activity-canvas :deep(.activity-edge.aside path.vue-flow__edge-path) {
  stroke: var(--border);
  stroke-dasharray: 5 4;
  stroke-width: 1.5;
}
.activity-canvas :deep(.vue-flow__arrowhead polyline) {
  stroke: var(--muted);
  fill: var(--muted);
}
.activity-canvas :deep(.vue-flow__controls) {
  box-shadow: none;
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
}
.tone-start,
.tone-note,
.activity-canvas :deep(.edge-start),
.activity-canvas :deep(.edge-note) {
  --tone-ink: var(--muted);
  --tone-soft: var(--surface-3);
  --tone-line: var(--border);
}
.tone-progress,
.activity-canvas :deep(.edge-progress) {
  --tone-ink: var(--teal-ink);
  --tone-soft: var(--teal-soft);
  --tone-line: var(--teal-line);
}
.tone-done,
.activity-canvas :deep(.edge-done) {
  --tone-ink: var(--green-ink);
  --tone-soft: var(--green-soft);
  --tone-line: var(--green-line);
}
.tone-warn,
.activity-canvas :deep(.edge-warn) {
  --tone-ink: var(--amber-ink);
  --tone-soft: var(--amber-soft);
  --tone-line: var(--amber-line);
}
.tone-stop,
.activity-canvas :deep(.edge-stop) {
  --tone-ink: var(--red-ink);
  --tone-soft: var(--red-soft);
  --tone-line: var(--red-line);
}
</style>
