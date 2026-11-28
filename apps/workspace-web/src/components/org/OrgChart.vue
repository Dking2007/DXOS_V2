<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<!-- Top-down org chart: drag to pan, wheel or pinch to zoom, branches fold, cards open details. -->
<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch, watchEffect } from 'vue'
import {
  Building2,
  ChevronsDownUp,
  ChevronsUpDown,
  Download,
  ImageDown,
  Maximize,
  TriangleAlert,
  Users,
  ZoomIn,
  ZoomOut,
} from 'lucide-vue-next'
import type { User } from '@dx/web-shared/types.ts'
import { toast } from '../../ui/toast'
import HighlightText from './HighlightText.vue'
import OrgAvatar from './OrgAvatar.vue'
import {
  CHART_SIZE,
  chartSvg,
  fitView,
  layoutChart,
  zoomAt,
  type LayoutInput,
  type SvgCard,
} from './orgLayout'
import { ROOT_ID, UNASSIGNED_ID, WARNING_LABELS, type OrgNode, type OrgSearch, type OrgTree } from './orgTree'

const props = defineProps<{
  tree: OrgTree
  rootTitle: string
  query: string
  search: OrgSearch
  attention: Set<string> | null
  selected: string | null
}>()
const emit = defineEmits<{ open: [id: string] }>()

const SIZE = CHART_SIZE
// Large organisations open folded below the second level so the first view stays readable.
const collapsed = ref(new Set<string>())
function defaultCollapsed() {
  if (props.tree.byId.size <= 24) return new Set<string>()
  return new Set([...props.tree.byId.values()].filter((node) => node.depth >= 2 && node.children.length).map((node) => node.id))
}
collapsed.value = defaultCollapsed()

function toInput(node: OrgNode): LayoutInput {
  return { id: node.id, children: node.children.map(toInput) }
}
const input = computed<LayoutInput>(() => ({
  id: ROOT_ID,
  children: [
    ...props.tree.roots.map(toInput),
    ...(props.tree.unassigned.length ? [{ id: UNASSIGNED_ID, children: [] }] : []),
  ],
}))
const layout = computed(() => layoutChart(input.value, collapsed.value, SIZE))
const childCount = (id: string) =>
  id === ROOT_ID ? input.value.children.length : (props.tree.byId.get(id)?.children.length ?? 0)

function toggle(id: string) {
  const next = new Set(collapsed.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  collapsed.value = next
}
function expandAll() {
  collapsed.value = new Set()
}
function collapseAll() {
  collapsed.value = new Set(props.tree.roots.filter((node) => node.children.length).map((node) => node.id))
}
const allOpen = computed(() => collapsed.value.size === 0)

// ---- Pan and zoom ----
const viewport = ref<HTMLElement>()
const view = ref({ scale: 1, x: 0, y: 0 })
const box = ref({ width: 0, height: 0 })
let observer: ResizeObserver | null = null
let fitted = false
function measure() {
  const rect = viewport.value?.getBoundingClientRect()
  if (rect) box.value = { width: rect.width, height: rect.height }
}
function fit() {
  measure()
  if (!box.value.width) return
  view.value = fitView(layout.value, box.value)
  fitted = true
}
function zoomBy(factor: number) {
  measure()
  view.value = zoomAt(view.value, factor, box.value.width / 2, box.value.height / 2)
}
function actualSize() {
  zoomBy(1 / view.value.scale)
}
function centerOn(id: string) {
  const target = layout.value.boxes.find((item) => item.id === id)
  if (!target) return
  measure()
  const { scale } = view.value
  view.value = {
    scale,
    x: box.value.width / 2 - (target.x + SIZE.width / 2) * scale,
    y: box.value.height / 2 - (target.y + SIZE.height / 2) * scale,
  }
}
onMounted(() => {
  measure()
  fit()
  observer = new ResizeObserver(() => {
    measure()
    if (!fitted) fit()
  })
  if (viewport.value) observer.observe(viewport.value)
})
onBeforeUnmount(() => observer?.disconnect())

const pointers = new Map<number, { x: number; y: number }>()
let drag: { x: number; y: number; vx: number; vy: number; moved: boolean } | null = null
let pinch: { distance: number } | null = null
let swallowClick = false
function local(event: { clientX: number; clientY: number }) {
  const rect = viewport.value!.getBoundingClientRect()
  return { x: event.clientX - rect.left, y: event.clientY - rect.top }
}
function onPointerDown(event: PointerEvent) {
  if (event.pointerType === 'mouse' && event.button !== 0) return
  swallowClick = false
  pointers.set(event.pointerId, { x: event.clientX, y: event.clientY })
  if (pointers.size === 1) drag = { x: event.clientX, y: event.clientY, vx: view.value.x, vy: view.value.y, moved: false }
  if (pointers.size === 2) {
    const [a, b] = [...pointers.values()]
    pinch = { distance: Math.hypot(a.x - b.x, a.y - b.y) }
    drag = null
  }
}
function onPointerMove(event: PointerEvent) {
  if (!pointers.has(event.pointerId)) return
  pointers.set(event.pointerId, { x: event.clientX, y: event.clientY })
  if (pinch && pointers.size === 2) {
    const [a, b] = [...pointers.values()]
    const distance = Math.hypot(a.x - b.x, a.y - b.y)
    const middle = local({ clientX: (a.x + b.x) / 2, clientY: (a.y + b.y) / 2 })
    view.value = zoomAt(view.value, distance / Math.max(1, pinch.distance), middle.x, middle.y)
    pinch.distance = distance
    swallowClick = true
    return
  }
  if (!drag) return
  const dx = event.clientX - drag.x
  const dy = event.clientY - drag.y
  // A small wobble is still a click on a card.
  if (!drag.moved && Math.hypot(dx, dy) < 5) return
  if (!drag.moved) {
    drag.moved = true
    viewport.value?.setPointerCapture(event.pointerId)
  }
  view.value = { ...view.value, x: drag.vx + dx, y: drag.vy + dy }
}
function onPointerUp(event: PointerEvent) {
  pointers.delete(event.pointerId)
  if (drag?.moved) swallowClick = true
  if (pointers.size < 2) pinch = null
  if (!pointers.size) drag = null
}
function onClickCapture(event: MouseEvent) {
  if (!swallowClick) return
  swallowClick = false
  event.stopPropagation()
  event.preventDefault()
}
function onWheel(event: WheelEvent) {
  const point = local(event)
  const delta = event.deltaMode === 1 ? event.deltaY * 16 : event.deltaY
  view.value = zoomAt(view.value, Math.exp(-delta * 0.0015), point.x, point.y)
}
function onKey(event: KeyboardEvent) {
  if (event.target !== viewport.value) return
  const step = 48
  const moves: Record<string, [number, number]> = {
    ArrowLeft: [step, 0],
    ArrowRight: [-step, 0],
    ArrowUp: [0, step],
    ArrowDown: [0, -step],
  }
  if (moves[event.key]) {
    const [dx, dy] = moves[event.key]
    view.value = { ...view.value, x: view.value.x + dx, y: view.value.y + dy }
  } else if (event.key === '+' || event.key === '=') zoomBy(1.2)
  else if (event.key === '-') zoomBy(1 / 1.2)
  else if (event.key === '0') fit()
  else return
  event.preventDefault()
}

// ---- Search: open the branches holding a match and bring the first one into view ----
watch(
  () => props.search,
  async (search) => {
    if (!props.query.trim()) return
    if (search.expand.size) collapsed.value = new Set([...collapsed.value].filter((id) => !search.expand.has(id)))
    await nextTick()
    const first = layout.value.boxes.find((item) => matched(item.id))
    if (first) centerOn(first.id)
  },
)
const selectedId = computed(() => props.selected)
watch(selectedId, async (id) => {
  if (!id || !props.tree.byId.has(id)) return
  const above: string[] = []
  let current = props.tree.byId.get(id)?.parentId
  while (current && !above.includes(current)) {
    above.push(current)
    current = props.tree.byId.get(current)?.parentId
  }
  if (above.some((item) => collapsed.value.has(item)))
    collapsed.value = new Set([...collapsed.value].filter((item) => !above.includes(item)))
})

function matched(id: string) {
  if (props.search.departments.has(id)) return true
  const node = props.tree.byId.get(id)
  if (node) return node.members.some((user) => props.search.members.has(user.id))
  if (id === ROOT_ID) return props.tree.board.some((user) => props.search.members.has(user.id))
  if (id === UNASSIGNED_ID) return props.tree.unassigned.some((user) => props.search.members.has(user.id))
  return false
}
function dimmed(id: string) {
  if (props.query.trim()) return !matched(id)
  if (props.attention) return id !== ROOT_ID && !props.attention.has(id)
  return false
}

// ---- What each card says ----
interface CardView {
  title: string
  code: string
  leader: User | null
  leaderText: string
  people: number
  peopleHint: string
  units: number
  warnings: string[]
  danger: boolean
  avatars: User[]
}
const cards = computed<Record<string, CardView>>(() => {
  const result: Record<string, CardView> = {
    [ROOT_ID]: {
      title: props.rootTitle,
      code: '',
      leader: props.tree.board[0] ?? null,
      leaderText: props.tree.board.length
        ? props.tree.board.map((user) => user.display_name).join(', ')
        : 'Chưa có Ban giám đốc',
      people: props.tree.users.length,
      peopleHint: 'người trong tổ chức',
      units: props.tree.roots.length,
      warnings: [],
      danger: false,
      avatars: props.tree.board.slice(0, 3),
    },
  }
  if (props.tree.unassigned.length)
    result[UNASSIGNED_ID] = {
      title: 'Chưa xếp phòng',
      code: '',
      leader: null,
      leaderText: 'Cần xếp vào một phòng ban',
      people: props.tree.unassigned.length,
      peopleHint: 'người chưa thuộc phòng nào',
      units: 0,
      warnings: [],
      danger: false,
      avatars: props.tree.unassigned.slice(0, 3),
    }
  for (const node of props.tree.byId.values())
    result[node.id] = {
      title: node.department.name,
      code: node.department.code ?? '',
      leader: node.leader,
      leaderText: node.leader?.display_name ?? 'Chưa có lãnh đạo',
      people: node.members.length,
      peopleHint:
        node.totalMembers > node.members.length
          ? `người · ${node.totalMembers} cả khối`
          : 'người',
      units: node.children.length,
      warnings: node.warnings.map((warning) => WARNING_LABELS[warning]),
      danger: node.warnings.includes('cycle') || node.warnings.includes('missing_parent'),
      avatars: [],
    }
  return result
})
function cardLabel(id: string) {
  const card = cards.value[id]
  if (!card) return ''
  const parts = [card.title, card.leaderText, `${card.people} ${card.peopleHint}`]
  if (card.units) parts.push(`${card.units} phòng con`)
  if (card.warnings.length) parts.push(`Cảnh báo: ${card.warnings.join(', ')}`)
  return `${parts.join('. ')}. Mở chi tiết`
}

// ---- Export ----
const exporting = ref(false)
function svgText() {
  const style = getComputedStyle(viewport.value ?? document.documentElement)
  const token = (name: string, fallback: string) => style.getPropertyValue(name).trim() || fallback
  const svgCards: Record<string, SvgCard> = {}
  for (const [id, card] of Object.entries(cards.value))
    svgCards[id] = {
      title: card.title,
      subtitle: [card.code, card.leaderText].filter(Boolean).join(' · '),
      meta: `${card.people} ${card.peopleHint}${card.units ? ` · ${card.units} phòng con` : ''}`,
      warning: card.warnings[0],
    }
  return chartSvg(
    layout.value,
    svgCards,
    {
      background: token('--canvas', 'white'),
      surface: token('--surface', 'white'),
      border: token('--border', 'gray'),
      text: token('--navy', 'black'),
      muted: token('--muted', 'gray'),
      accent: token('--teal', 'navy'),
      warning: token('--amber-ink', 'darkorange'),
      line: token('--border-strong', 'gray'),
      font: style.fontFamily || 'sans-serif',
    },
    SIZE,
  )
}
function download(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = name
  document.body.append(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
function exportSvg() {
  download(new Blob([svgText()], { type: 'image/svg+xml' }), 'so-do-to-chuc.svg')
}
async function exportPng() {
  exporting.value = true
  const source = URL.createObjectURL(new Blob([svgText()], { type: 'image/svg+xml' }))
  try {
    const image = new Image()
    await new Promise<void>((resolve, reject) => {
      image.onload = () => resolve()
      image.onerror = () => reject(new Error('Không dựng được ảnh sơ đồ.'))
      image.src = source
    })
    const ratio = Math.min(2, 16000 / Math.max(image.width, image.height))
    const canvas = document.createElement('canvas')
    canvas.width = Math.round(image.width * ratio)
    canvas.height = Math.round(image.height * ratio)
    const context = canvas.getContext('2d')
    if (!context) throw new Error('Trình duyệt không hỗ trợ xuất ảnh.')
    context.scale(ratio, ratio)
    context.drawImage(image, 0, 0)
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/png'))
    if (!blob) throw new Error('Ảnh sơ đồ quá lớn để xuất. Hãy thử tải SVG.')
    download(blob, 'so-do-to-chuc.png')
  } catch (error) {
    toast.error(error)
  } finally {
    URL.revokeObjectURL(source)
    exporting.value = false
  }
}
const percent = computed(() => `${Math.round(view.value.scale * 100)}%`)
const atMinScale = computed(() => view.value.scale <= 0.26)
const atMaxScale = computed(() => view.value.scale >= 1.99)
// Panning changes the view on every pointer move. The stage is moved directly instead of through
// the template, so a pan does not rebuild every card; only the zoom readout above re-renders.
const stage = ref<HTMLElement>()
watchEffect(
  () => {
    const { x, y, scale } = view.value
    if (stage.value) stage.value.style.transform = `translate(${x}px, ${y}px) scale(${scale})`
  },
  { flush: 'post' },
)
</script>
<template>
  <div class="org-chart">
    <div class="org-chart-tools" role="toolbar" aria-label="Điều khiển sơ đồ">
      <div class="org-tool-group">
        <button class="icon-button" type="button" aria-label="Thu nhỏ" title="Thu nhỏ (−)" :disabled="atMinScale" @click="zoomBy(1 / 1.2)">
          <ZoomOut :size="18" />
        </button>
        <button class="org-zoom-value" type="button" title="Về cỡ thật 100%" aria-label="Về cỡ thật 100%" @click="actualSize">
          {{ percent }}
        </button>
        <button class="icon-button" type="button" aria-label="Phóng to" title="Phóng to (+)" :disabled="atMaxScale" @click="zoomBy(1.2)">
          <ZoomIn :size="18" />
        </button>
        <button class="button secondary small" type="button" title="Hiện trọn sơ đồ (phím 0)" @click="fit">
          <Maximize :size="16" />Vừa khung
        </button>
      </div>
      <div class="org-tool-group">
        <button class="button ghost small" type="button" :disabled="allOpen" :title="allOpen ? 'Mọi nhánh đang mở' : 'Mở mọi nhánh'" @click="expandAll">
          <ChevronsUpDown :size="16" />Mở hết
        </button>
        <button class="button ghost small" type="button" @click="collapseAll"><ChevronsDownUp :size="16" />Thu gọn</button>
      </div>
      <div class="org-tool-group org-tool-end">
        <button class="button ghost small" type="button" title="Tải sơ đồ dạng SVG (vector)" @click="exportSvg">
          <Download :size="16" />SVG
        </button>
        <button class="button ghost small" type="button" title="Tải sơ đồ dạng ảnh PNG" :disabled="exporting" @click="exportPng">
          <ImageDown :size="16" />{{ exporting ? 'Đang xuất…' : 'PNG' }}
        </button>
      </div>
    </div>
    <div
      ref="viewport"
      class="org-viewport"
      tabindex="0"
      role="region"
      aria-label="Sơ đồ tổ chức. Kéo để di chuyển, cuộn chuột để phóng to, phím mũi tên để di chuyển, phím 0 để vừa khung."
      @pointerdown="onPointerDown"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
      @pointercancel="onPointerUp"
      @click.capture="onClickCapture"
      @wheel.prevent="onWheel"
      @keydown="onKey"
    >
      <div ref="stage" class="org-stage" :style="{ width: `${layout.width}px`, height: `${layout.height}px` }">
        <svg class="org-lines" :width="layout.width" :height="layout.height" aria-hidden="true">
          <path v-for="edge in layout.edges" :key="`${edge.from}-${edge.to}`" :d="edge.path" />
        </svg>
        <div
          v-for="item in layout.boxes"
          :key="item.id"
          class="org-node"
          :class="{
            root: item.id === ROOT_ID,
            bucket: item.id === UNASSIGNED_ID,
            selected: selected === item.id,
            dim: dimmed(item.id),
            hit: query.trim() && matched(item.id),
            warn: cards[item.id]?.warnings.length,
            danger: cards[item.id]?.danger,
          }"
          :style="{ width: `${SIZE.width}px`, height: `${SIZE.height}px`, transform: `translate(${item.x}px, ${item.y}px)` }"
        >
          <button class="org-node-main" type="button" :aria-label="cardLabel(item.id)" @click="emit('open', item.id)">
            <span class="org-node-head">
              <strong
                class="org-ellipsis"
                :title="[cards[item.id]?.title, cards[item.id]?.code].filter(Boolean).join(' · ')"
                ><HighlightText :text="cards[item.id]?.title ?? ''" :query="query"
              /></strong>
            </span>
            <span class="org-node-leader">
              <span v-if="cards[item.id]?.avatars.length" class="org-avatars">
                <OrgAvatar v-for="person in cards[item.id]?.avatars" :key="person.id" :user="person" />
              </span>
              <OrgAvatar v-else-if="item.id !== UNASSIGNED_ID" :user="cards[item.id]?.leader ?? null" />
              <span
                class="org-ellipsis"
                :class="{ missing: !cards[item.id]?.leader && item.id !== UNASSIGNED_ID }"
                :title="cards[item.id]?.leaderText"
                >{{ cards[item.id]?.leaderText }}</span
              >
            </span>
            <span class="org-node-meta">
              <span :title="`${cards[item.id]?.people} ${cards[item.id]?.peopleHint}`"
                ><Users :size="14" aria-hidden="true" />{{ cards[item.id]?.people }}
                <small>{{ cards[item.id]?.peopleHint }}</small></span
              >
              <span v-if="cards[item.id]?.units" :title="`${cards[item.id]?.units} phòng con`"
                ><Building2 :size="14" aria-hidden="true" />{{ cards[item.id]?.units }}</span
              >
            </span>
            <span v-if="cards[item.id]?.warnings.length" class="org-badges">
              <span class="org-badge" :class="cards[item.id]?.danger ? 'danger' : 'warn'" :title="cards[item.id]?.warnings.join(' · ')"
                ><TriangleAlert :size="12" aria-hidden="true" />{{ cards[item.id]?.warnings[0] }}</span
              ><span v-if="(cards[item.id]?.warnings.length ?? 0) > 1" class="org-badge warn" :title="cards[item.id]?.warnings.join(' · ')"
                >+{{ (cards[item.id]?.warnings.length ?? 0) - 1 }}</span
              >
            </span>
          </button>
          <button
            v-if="childCount(item.id) && item.id !== ROOT_ID"
            class="org-node-toggle"
            type="button"
            :aria-expanded="!collapsed.has(item.id)"
            :aria-label="`${collapsed.has(item.id) ? 'Mở' : 'Thu gọn'} nhánh ${cards[item.id]?.title}`"
            :title="collapsed.has(item.id) ? `Mở ${item.hidden} phòng con` : 'Thu gọn nhánh'"
            @click="toggle(item.id)"
          >
            {{ collapsed.has(item.id) ? `+${item.hidden}` : '−' }}
          </button>
        </div>
      </div>
      <p class="org-chart-hint" aria-hidden="true">Kéo để di chuyển · Cuộn chuột hoặc chụm hai ngón để phóng to</p>
    </div>
  </div>
</template>
<style scoped>
.org-chart {
  display: grid;
}
.org-chart-tools {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 16px;
  padding: 12px 24px;
  border-bottom: 1px solid var(--border);
}
.org-tool-group {
  display: flex;
  align-items: center;
  gap: 4px;
}
.org-tool-end {
  margin-left: auto;
}
.org-zoom-value {
  min-width: 56px;
  min-height: 36px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: var(--ink-2);
  font-size: 0.875rem;
  font-variant-numeric: tabular-nums;
}
.org-zoom-value:hover {
  background: var(--surface-3);
}
.org-viewport {
  position: relative;
  height: clamp(420px, 64vh, 760px);
  overflow: hidden;
  cursor: grab;
  touch-action: none;
  background-color: var(--canvas);
  background-image: radial-gradient(circle, var(--border) 1px, transparent 1px);
  background-size: 20px 20px;
  user-select: none;
}
.org-viewport:active {
  cursor: grabbing;
}
.org-viewport:focus-visible {
  outline: 2px solid var(--focus);
  outline-offset: -2px;
}
.org-stage {
  position: absolute;
  top: 0;
  left: 0;
  transform-origin: 0 0;
}
.org-lines {
  position: absolute;
  inset: 0;
  overflow: visible;
  pointer-events: none;
}
.org-lines path {
  fill: none;
  stroke: var(--border-strong);
  stroke-width: 1.5;
}
.org-node {
  position: absolute;
  top: 0;
  left: 0;
  transition: opacity 0.18s;
}
.org-node.dim {
  opacity: 0.4;
}
.org-node-main {
  display: grid;
  align-content: start;
  gap: 8px;
  width: 100%;
  height: 100%;
  padding: 12px 16px 12px 18px;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--surface);
  color: var(--navy);
  text-align: left;
  box-shadow: var(--shadow-sm);
  position: relative;
  overflow: hidden;
  transition:
    border-color 0.15s,
    box-shadow 0.15s,
    transform 0.15s;
}
/* A coloured edge marks what kind of card this is. */
.org-node-main::before {
  content: '';
  position: absolute;
  left: 0;
  top: 12px;
  bottom: 12px;
  width: 4px;
  border-radius: 0 4px 4px 0;
  background: var(--teal);
}
.org-node.warn .org-node-main::before {
  background: var(--amber);
}
.org-node.danger .org-node-main::before {
  background: var(--red);
}
.org-node.bucket .org-node-main {
  border-style: dashed;
  background: var(--surface-2);
}
.org-node.bucket .org-node-main::before {
  background: var(--muted);
}
.org-node.root .org-node-main {
  background: var(--teal-soft);
  border-color: var(--teal-line);
}
.org-node-main:hover {
  border-color: var(--border-strong);
  box-shadow: var(--shadow-md);
  transform: translateY(-1px);
}
.org-node.selected .org-node-main {
  border-color: var(--teal);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--teal) 22%, transparent);
}
.org-node.hit .org-node-main {
  border-color: var(--amber);
}
.org-node-head {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.org-node-head strong {
  flex: 1;
  font-family: 'Be Vietnam Pro', sans-serif;
  font-size: 0.9375rem;
  font-weight: 600;
  line-height: 1.4;
}
.org-node-leader {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  font-size: 0.875rem;
  color: var(--ink-2);
}
.org-node-leader .missing {
  color: var(--amber-ink);
}
.org-node-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--ink-2);
  font-variant-numeric: tabular-nums;
}
.org-node-meta > span {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
  white-space: nowrap;
}
.org-node-meta > span:first-child {
  overflow: hidden;
}
.org-node-meta small {
  overflow: hidden;
  text-overflow: ellipsis;
  font-weight: 400;
  font-size: 0.8125rem;
  color: var(--muted);
}
.org-node-meta svg {
  color: var(--muted);
}
.org-node-toggle {
  position: absolute;
  left: 50%;
  bottom: -14px;
  transform: translateX(-50%);
  min-width: 28px;
  height: 28px;
  padding: 0 8px;
  border: 1px solid var(--border-strong);
  border-radius: 999px;
  background: var(--surface);
  color: var(--ink-2);
  font-size: 0.8125rem;
  font-weight: 700;
  line-height: 1;
  box-shadow: var(--shadow-sm);
  transition:
    background 0.15s,
    color 0.15s;
}
/* A larger invisible hit area than the visible pill. */
.org-node-toggle::after {
  content: '';
  position: absolute;
  inset: -6px;
}
.org-node-toggle:hover {
  background: var(--teal-soft);
  color: var(--teal-ink);
}
.org-chart-hint {
  position: absolute;
  right: 12px;
  bottom: 8px;
  margin: 0;
  padding: 4px 8px;
  border-radius: 6px;
  background: color-mix(in srgb, var(--surface) 88%, transparent);
  color: var(--muted);
  font-size: 0.75rem;
  pointer-events: none;
}
@media (max-width: 640px) {
  .org-chart-tools {
    padding: 12px 16px;
  }
  .org-tool-end {
    margin-left: 0;
  }
  .org-viewport {
    height: 60vh;
  }
  .org-chart-hint {
    display: none;
  }
}
@media (prefers-reduced-motion: reduce) {
  :root:not([data-motion='full']) .org-node-main:hover {
    transform: none;
  }
}
:root[data-motion='reduce'] .org-node-main:hover {
  transform: none;
}
</style>
