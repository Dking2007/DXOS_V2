<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, provide, ref, watch } from 'vue'
import type { Ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { useUnsavedGuard } from '../ui/unsaved'
import { useDebounced } from '../ui/debounced'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import type { Connection, Edge, Node } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { MiniMap } from '@vue-flow/minimap'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/minimap/dist/style.css'
import '../flow/flow.css'
import {
  AlertTriangle,
  AlignCenterHorizontal,
  AlignHorizontalDistributeCenter,
  AlignStartVertical,
  AlignVerticalDistributeCenter,
  ArrowLeft,
  BoxSelect,
  CheckCircle2,
  ChevronDown,
  ClipboardPaste,
  Copy,
  CopyPlus,
  FlaskConical,
  Grid3x3,
  History,
  Info,
  Keyboard,
  Map as MapIcon,
  Maximize,
  Network,
  PanelBottomClose,
  Play,
  PlayCircle,
  Plus,
  Power,
  Redo2,
  Save,
  Scissors,
  Search,
  Trash2,
  Undo2,
  Unlink,
  X,
  Zap,
  ZoomIn,
  ZoomOut,
  FilePen,
  Rocket,
} from 'lucide-vue-next'
import ModalDialog from '@dx/web-shared/components/ModalDialog.vue'
import { api } from '../api'
import { ApiError, errorText, formatDate } from '@dx/web-shared/api.ts'
import type { Page } from '@dx/web-shared/api.ts'
import type { Department, FormTemplate, User } from '@dx/web-shared/types.ts'
import StatusBadge from '@dx/web-shared/components/StatusBadge.vue'
import StatePanel from '@dx/web-shared/components/StatePanel.vue'
import FlowNode from '../flow/FlowNode.vue'
import FlowEdge from '../flow/FlowEdge.vue'
import CanvasMenu from '../flow/CanvasMenu.vue'
import type { MenuItem } from '../flow/CanvasMenu.vue'
import ShortcutHelp from '../flow/ShortcutHelp.vue'
import StepPicker from '../flow/StepPicker.vue'
import { useCanvasEditing } from '../flow/useCanvasEditing'
import { FIT_VIEW, makeRoom } from '../flow/layout'
import type { Point } from '../flow/layout'
import { isMac, isTypingTarget, shortcutFor } from '../flow/shortcuts'
import NodeInspector from '../flow/NodeInspector.vue'
import ProcessFormDialog from '../flow/ProcessFormDialog.vue'
import ProcessPanel from '../flow/ProcessPanel.vue'
import { FLOW_CONTEXT } from '../flow/context'
import {
  KINDS,
  OUTCOMES,
  nodeOutputs,
  plainCopy,
  TEMPLATES,
  canvasEdge,
  outputs,
  paintRun,
  paletteKinds,
  toApi,
  toCanvas,
  tone,
} from '../flow/nodes'
import { useAi } from '../ai/useAi'
import { fetchPackTemplates } from '../flow/templates'
import { pluginStepConfig, usePluginSteps } from '../flow/pluginNodes'
import type { PluginStep } from '../flow/pluginNodes'
import { fold } from '@dx/web-shared/text.ts'
import type { ApiGraph, FlowKind, FlowNodeData, NodeKind, RunStep, TriggerInfo } from '../flow/nodes'
type Step = RunStep & { error?: string; recipients?: string[] }
interface ProcessForm {
  id: string
  name: string
  fields: Record<string, string>
}
interface Run {
  id: string
  state: string
  event_type: string
  steps: Step[]
  data: Record<string, unknown> | null
  created_at: string
  subject: { type: 'task' | 'case' | 'post'; id: string; title: string; link: string | null } | null
  manual_by: string | null
}
interface Rule {
  id: string
  name: string
  description: string
  enabled: boolean
  active_version_no?: number | null
  revision: number
  graph: ApiGraph
  scope: 'all' | 'attached'
  attached_count: number
  kind: FlowKind
}
interface Catalog {
  triggers: TriggerInfo[]
  webhooks_enabled: boolean
  max_nodes: number
  process: {
    fields: Record<string, string>
    sample: Record<string, unknown>
    forms: ProcessForm[]
    subprocesses?: { id: string; name: string }[]
  }
}
const route = useRoute()
const router = useRouter()
const queryClient = useQueryClient()
const ruleId = ref(route.params.id === 'new' ? '' : String(route.params.id))
// Reference data the designer only reads: no need to refetch it each time the window regains focus.
const REFERENCE_STALE = 60_000
const catalog = useQuery({
  queryKey: ['automations', 'catalog'],
  queryFn: () => api.request<Catalog>('/automations/catalog'),
  staleTime: REFERENCE_STALE,
})
const users = useQuery({
  queryKey: ['users'],
  queryFn: () => api.request<Page<User>>('/users'),
  staleTime: REFERENCE_STALE,
})
const departments = useQuery({
  queryKey: ['departments'],
  queryFn: () => api.request<Page<Department>>('/departments'),
  staleTime: REFERENCE_STALE,
})
const connections = useQuery({
  queryKey: ['connections'],
  queryFn: () => api.request<Page<{ id: string; name: string; base_url: string }>>('/connections'),
  staleTime: REFERENCE_STALE,
})
/** Shared empty list for props, so a child does not see a "new" array on every render while loading. */
const NONE: never[] = []
const triggers = computed(() => catalog.data.value?.triggers ?? [])
function userName(id: string) {
  return users.data.value?.items.find((u) => u.id === id)?.display_name ?? id.slice(0, 8)
}

// A form on the trigger makes the flow the route of that form's dossiers; nothing else differs.
const isProcess = computed(() => !!triggerNode.value?.data?.config.form_id)
const forms = computed(() => catalog.data.value?.process.forms ?? [])
/** Other processes this one can start; a computed so the inspector is not handed a new list each render. */
const subprocesses = computed(() =>
  catalog.data.value?.process.subprocesses?.filter((item) => item.id !== ruleId.value),
)
const name = ref('Quy trình mới')
const description = ref('')
const scope = ref<'all' | 'attached'>('all')
const attachedCount = ref(0)
const enabled = ref(false)
const activeVersion = ref<number | null>(null)
const panelOpen = ref(false)
const editingForm = ref(false)
const revision = ref(0)
// Typed through `Ref` directly: unwrapping Vue Flow's node type recursively is too deep for TS.
const nodes = ref([]) as Ref<Node<FlowNodeData>[]>
const edges = ref([]) as Ref<Edge[]>
const saved = ref('')
const selectedId = ref<string | null>(null)
const busy = ref(false)
const error = ref<unknown>(null)
const notice = ref('')
const flow = useVueFlow({ id: 'automation-flow' })
const {
  fitView,
  screenToFlowCoordinate,
  onConnect,
  onNodeClick,
  onPaneClick,
  onEdgeClick,
  onNodesInitialized,
  viewport,
  dimensions,
} = flow

let baselinePending = false
function load(graph: ApiGraph) {
  const canvas = toCanvas(graph)
  nodes.value = canvas.nodes
  edges.value = canvas.edges
  baselinePending = true
}
// The canvas may snap positions to the grid while it lays nodes out; the "saved" baseline is
// taken after that, so opening a flow never shows it as changed.
onNodesInitialized(() => {
  if (!baselinePending) return
  baselinePending = false
  nextTick(() => {
    saved.value = snapshot()
    editing.history.reset()
    void editing.fitOpening()
  })
})
// The graph part comes from the editing helper's JSON, which is already kept up to date (and
// held still while steps are dragged), instead of serialising the graph a second time.
function snapshot() {
  return JSON.stringify({
    g: editing.graphJson.value,
    n: name.value,
    d: description.value,
    s: scope.value,
  })
}
const dirty = computed(() => saved.value !== '' && snapshot() !== saved.value)
if (ruleId.value) {
  api
    .request<Rule>(`/automations/${ruleId.value}`)
    .then((rule) => {
      name.value = rule.name
      description.value = rule.description
      enabled.value = rule.enabled
      activeVersion.value = rule.active_version_no ?? null
      revision.value = rule.revision
      scope.value = rule.scope
      attachedCount.value = rule.attached_count
      load(rule.graph)
    })
    .catch((cause) => (error.value = cause))
} else if (route.query.from_form) {
  // Start from the form's own approval steps, redrawn on the canvas.
  api
    .request<{ name: string; graph: ApiGraph }>(
      `/automations/process-template?form_id=${encodeURIComponent(String(route.query.from_form))}`,
    )
    .then((template) => {
      name.value = template.name
      load(template.graph)
    })
    .catch((cause) => (error.value = cause))
} else {
  const wanted = route.query.template ? String(route.query.template) : ''
  const builtIn = TEMPLATES.find((t) => t.key === wanted)
  // Process templates live in the installed sector packs; event flows ship with the app.
  if (builtIn || !wanted) startFrom(builtIn ?? TEMPLATES[0]!)
  else
    fetchPackTemplates()
      .then((items) => startFrom(items.find((t) => t.key === wanted) ?? TEMPLATES[0]!))
      .catch((cause) => (error.value = cause))
}
function startFrom(template: { key: string; title: string; graph: ApiGraph }) {
  if (template.key !== 'blank') name.value = template.title
  const graph = plainCopy(template.graph)
  if (route.query.form) {
    const start = graph.nodes.find((node) => node.type === 'trigger')
    if (start) start.data = { ...start.data, form_id: String(route.query.form) }
  }
  load(graph)
}

const selected = computed(() => nodes.value.find((node) => node.id === selectedId.value) ?? null)
const infoOpen = ref(false)
// Only offered on phones, where the strip costs a fifth of the screen.
const statusClosed = ref(false)
watch(selectedId, (id) => id && (infoOpen.value = false))
const triggerNode = computed(() => nodes.value.find((node) => node.data?.kind === 'trigger'))
const processForm = computed(() => forms.value.find((f) => f.id === triggerNode.value?.data?.config.form_id))
/** A process always starts when a dossier of its form is submitted. */
const processTrigger = computed<TriggerInfo>(() => ({
  ...triggers.value.find((item) => item.key === 'case.submitted'),
  key: 'case.submitted',
  label: processForm.value ? `hồ sơ “${processForm.value.name}” được trình` : 'hồ sơ được trình',
  fields: { ...(catalog.data.value?.process.fields ?? {}), ...(processForm.value?.fields ?? {}) },
  sample: catalog.data.value?.process.sample ?? {},
}))
const trigger = computed(() =>
  isProcess.value ? processTrigger.value : triggers.value.find((t) => t.key === triggerNode.value?.data?.config.event),
)
// What earlier steps produce becomes fields that later conditions and text can read.
const fields = computed(() => ({
  ...(trigger.value?.fields ?? {}),
  ...(catalog.data.value && triggerNode.value?.data?.config.event === 'case.submitted'
    ? catalog.data.value.process.fields
    : {}),
  ...Object.assign(
    {},
    ...nodes.value.map((node) =>
      nodeOutputs(node.id, node.data!.kind, node.data!.config, node.data!.label || KINDS[node.data!.kind].title),
    ),
  ),
  ...Object.fromEntries(
    nodes.value
      .filter((node) => node.data?.kind === 'ai')
      .map((node) => [String(node.data!.config.output || 'ai_label'), `Kết quả AI: ${String(node.data!.config.question ?? '')}`]),
  ),
}))
/** Only task events after creation can be limited to tasks people attach the flow to. */
const attachable = computed(() => !!trigger.value?.attachable)
watch(attachable, (value) => !value && (scope.value = 'all'))
const attachedMode = computed(() => attachable.value && scope.value === 'attached')

// ---- Editing ----
let counter = 0
function newId(kind: NodeKind) {
  counter += 1
  return `${kind}_${Date.now().toString(36).slice(-4)}${counter}`
}
// Settings the next added node starts with instead of its kind's defaults (a plugin's step).
let nextConfig: Record<string, unknown> | null = null
const pluginSteps = usePluginSteps()
const pluginQuery = computed(() =>
  (pluginSteps.data.value ?? []).filter(
    (step) => !paletteQuery.value || fold(`${step.title} ${step.plugin_name}`).includes(fold(paletteQuery.value)),
  ),
)
function addPluginStep(step: PluginStep) {
  nextConfig = pluginStepConfig(step)
  addFromPalette('plugin_action')
}
function onPluginDragStart(event: DragEvent, step: PluginStep) {
  event.dataTransfer?.setData('application/dx-plugin', JSON.stringify(pluginStepConfig(step)))
  if (event.dataTransfer) event.dataTransfer.effectAllowed = 'move'
}
function addNode(
  kind: NodeKind,
  position: { x: number; y: number },
  after?: { id: string; handle?: string },
): string | null {
  if (kind === 'trigger' && triggerNode.value) {
    nextConfig = null
    notify('Mỗi luồng chỉ có một bước kích hoạt.')
    return null
  }
  if (nodes.value.length >= maxNodes()) {
    nextConfig = null
    notify('Luồng đã đạt số bước tối đa.')
    return null
  }
  const id = newId(kind)
  nodes.value = [
    ...nodes.value,
    {
      id,
      type: 'flow',
      position,
      data: { kind, label: '', config: nextConfig ?? KINDS[kind].defaults() },
      deletable: kind !== 'trigger',
    },
  ]
  nextConfig = null
  if (after) edges.value = [...edges.value, canvasEdge(after.id, id, after.handle)]
  selectedId.value = id
  editing.selectOnly([id])
  clearOverlay()
  return id
}
const maxNodes = () => catalog.data.value?.max_nodes ?? 40
/** A new step to the right of another, below the steps already hanging from it. */
function placeAfter(nodeId: string, handle: string | undefined, kind: NodeKind) {
  const from = nodes.value.find((node) => node.id === nodeId)
  if (!from) return
  const siblings = edges.value.filter((edge) => edge.source === from.id).length
  addNode(kind, { x: from.position.x + 360, y: from.position.y + siblings * 130 }, { id: nodeId, handle })
}
/** A new step in the middle of a connection; steps after it move right when there is no room. */
function placeOnEdge(edgeId: string, kind: NodeKind) {
  const edge = edges.value.find((item) => item.id === edgeId)
  const from = edge && nodes.value.find((node) => node.id === edge.source)
  const to = edge && nodes.value.find((node) => node.id === edge.target)
  if (!edge || !from || !to) return
  const plan = makeRoom(
    nodes.value.map((node) => ({ id: node.id, ...node.position })),
    edges.value,
    { id: from.id, ...from.position },
    { id: to.id, ...to.position },
  )
  const id = addNode(kind, plan.at)
  if (!id) return
  for (const [moved, position] of Object.entries(plan.moved)) flow.updateNode(moved, { position })
  const created = nodes.value.find((node) => node.id === id)!
  const exit = outputs(kind, created.data!.config)[0]
  edges.value = [
    ...edges.value.filter((item) => item.id !== edgeId),
    canvasEdge(edge.source, id, edge.sourceHandle),
    canvasEdge(id, edge.target, exit),
  ]
}

// ---- Step picker: "+" on a step or a connection, "Thêm bước…" in the menu, or the N key ----
type PickerTarget =
  | { mode: 'after'; id: string; handle?: string }
  | { mode: 'edge'; edgeId: string }
  | { mode: 'free'; at: Point }
const stage = ref<HTMLElement>()
const picker = ref<{ target: PickerTarget; x: number; y: number } | null>(null)
function openPicker(target: PickerTarget, anchor?: Point | null) {
  const box = stage.value?.getBoundingClientRect()
  menu.value = null
  helpOpen.value = false
  picker.value = {
    target,
    x: anchor && box ? anchor.x - box.left + 14 : (box?.width ?? 640) / 2 - 160,
    y: anchor && box ? anchor.y - box.top : 72,
  }
}
function addAfter(nodeId: string, handle?: string, anchor?: Point) {
  openPicker({ mode: 'after', id: nodeId, handle }, anchor)
}
function insertOnEdge(edgeId: string, anchor: Point) {
  openPicker({ mode: 'edge', edgeId }, anchor)
}
const pickerTitle = computed(() =>
  picker.value?.target.mode === 'edge'
    ? 'Chèn bước vào đường nối'
    : picker.value?.target.mode === 'after'
      ? 'Thêm bước tiếp theo'
      : 'Thêm bước',
)
/** A step that ends the flow cannot sit in the middle of a connection. */
const pickerKinds = computed(() =>
  picker.value?.target.mode === 'edge' ? offeredKinds.value.filter((kind) => !KINDS[kind].terminal) : offeredKinds.value,
)
function pick(kind: NodeKind, config?: Record<string, unknown>) {
  const target = picker.value?.target
  picker.value = null
  if (!target) return
  nextConfig = config ?? null
  if (target.mode === 'after') placeAfter(target.id, target.handle, kind)
  else if (target.mode === 'edge') placeOnEdge(target.edgeId, kind)
  else addNode(kind, target.at)
  nextConfig = null
}
/** N: a step after the one selected step, or where the pointer is. */
function openAddStep() {
  const only = editing.selectedIds()
  const base = only.length === 1 ? nodes.value.find((node) => node.id === only[0]) : undefined
  if (base?.data && !KINDS[base.data.kind].terminal) {
    const element = root.value?.querySelector(`.vue-flow__node[data-id="${CSS.escape(base.id)}"]`)
    const box = element?.getBoundingClientRect()
    openPicker(
      { mode: 'after', id: base.id, handle: freeHandle(base) },
      box ? { x: box.right + 40, y: box.top + box.height / 2 } : null,
    )
    return
  }
  openPicker({ mode: 'free', at: flowPoint(pointer.value ?? stageCenter()) }, pointer.value)
}

function onDragStart(event: DragEvent, kind: NodeKind) {
  event.dataTransfer?.setData('application/dx-node', kind)
  if (event.dataTransfer) event.dataTransfer.effectAllowed = 'move'
}
function onDrop(event: DragEvent) {
  const plugin = event.dataTransfer?.getData('application/dx-plugin')
  if (plugin) {
    nextConfig = JSON.parse(plugin) as Record<string, unknown>
    const at = screenToFlowCoordinate({ x: event.clientX, y: event.clientY })
    addNode('plugin_action', { x: at.x - 120, y: at.y - 36 })
    return
  }
  const kind = event.dataTransfer?.getData('application/dx-node') as NodeKind
  if (!kind || !(kind in KINDS)) return
  const point = screenToFlowCoordinate({ x: event.clientX, y: event.clientY })
  addNode(kind, { x: point.x - 120, y: point.y - 36 })
}
/** The exit a new step hangs from: the first branch still unconnected, else the first one. */
function freeHandle(node: Node<FlowNodeData>): string | undefined {
  const exits = outputs(node.data!.kind, node.data!.config)
  if (!exits.length) return undefined
  const used = new Set(edges.value.filter((edge) => edge.source === node.id).map((edge) => edge.sourceHandle))
  return exits.find((exit) => !used.has(exit)) ?? exits[0]
}
function addFromPalette(kind: NodeKind) {
  // Clicking places the node after the selected one, the way most people build a flow.
  const base = selected.value ?? nodes.value.at(-1)
  if (base?.data && !KINDS[base.data.kind].terminal && kind !== 'trigger') {
    placeAfter(base.id, freeHandle(base), kind)
  } else {
    addNode(kind, { x: (base?.position.x ?? 0) + 320, y: base?.position.y ?? 0 })
  }
}
function isValidConnection(connection: Connection) {
  if (connection.source === connection.target) return false
  const target = nodes.value.find((node) => node.id === connection.target)
  return target?.data?.kind !== 'trigger'
}
onConnect((connection) => {
  const edge = canvasEdge(connection.source, connection.target, connection.sourceHandle)
  if (!edges.value.some((item) => item.id === edge.id)) edges.value = [...edges.value, edge]
  clearOverlay()
})
onNodeClick(({ event, node }) => {
  // Ctrl/⌘/Shift-click builds a multi-selection instead of opening the step.
  const mouse = event as MouseEvent
  if (mouse.ctrlKey || mouse.metaKey || mouse.shiftKey) return
  selectedId.value = node.id
})
onPaneClick(() => {
  selectedId.value = null
  picker.value = null
  menu.value = null
})
onEdgeClick(() => (selectedId.value = null))
const hoveredEdge = ref<string | null>(null)
flow.onEdgeMouseEnter(({ edge }) => (hoveredEdge.value = edge.id))
flow.onEdgeMouseLeave(() => (hoveredEdge.value = null))
function patch(values: Record<string, unknown>) {
  if (!selected.value?.data) return
  selected.value.data = { ...selected.value.data, config: { ...selected.value.data.config, ...values } }
  clearOverlay()
}
function setLabel(value: string) {
  if (selected.value?.data) selected.value.data = { ...selected.value.data, label: value }
}
function removeSelected() {
  if (selectedId.value) editing.remove([selectedId.value])
}
function duplicateSelected() {
  if (!selectedId.value) return
  editing.selectOnly([selectedId.value])
  void nextTick(() => editing.duplicate())
}

// ---- Clipboard, undo, selection and the keyboard ----
let noticeTimer: ReturnType<typeof setTimeout> | undefined
const noticeUndo = ref(false)
/** Message on the canvas; an undoable change offers "Hoàn tác" for a little longer. */
function notify(text: string, undoable = false) {
  noticeUndo.value = undoable
  notice.value = text
  clearTimeout(noticeTimer)
  noticeTimer = setTimeout(() => (notice.value = ''), undoable ? 6000 : 2800)
}
const editing = useCanvasEditing({
  nodes,
  edges,
  flow,
  newId,
  maxNodes,
  current: () => selectedId.value,
  open: (id) => (selectedId.value = id),
  notify,
  beforeChange: () => clearOverlay(),
})
const { history } = editing
watch(
  () => editing.selectedNodes.value.length,
  (count) => count > 1 && (selectedId.value = null),
)
const mod = isMac() ? '⌘' : 'Ctrl'

// Where the pointer is over the canvas: pasting and adding steps happen there.
const pointer = ref<Point | null>(null)
function stageCenter(): Point {
  const box = stage.value?.getBoundingClientRect()
  return box ? { x: box.left + box.width / 2, y: box.top + box.height / 3 } : { x: 0, y: 0 }
}
function flowPoint(client: Point): Point {
  const at = screenToFlowCoordinate(client)
  return { x: Math.round(at.x), y: Math.round(at.y) }
}
let lastPaste = ''
let pasteStreak = 0
/** Pastes at the pointer; pasting again without moving it steps the copies down and right. */
function pasteAnchor(): Point | null {
  if (!pointer.value) return null
  const key = `${pointer.value.x},${pointer.value.y}`
  pasteStreak = key === lastPaste ? pasteStreak + 1 : 0
  lastPaste = key
  const at = flowPoint(pointer.value)
  return { x: at.x + pasteStreak * 40, y: at.y + pasteStreak * 40 }
}

const root = ref<HTMLElement>()
const helpOpen = ref(false)
function dialogOpen() {
  return !!document.querySelector('dialog[open]')
}
/** Shortcuts act on the editor itself (or when nothing is focused), never in other parts of the app. */
function inEditor(target: EventTarget | null) {
  return target === document.body || target === document.documentElement || !!root.value?.contains(target as globalThis.Node)
}
function hasTextSelection() {
  return !!window.getSelection()?.toString()
}
let pasteFallback: ReturnType<typeof setTimeout> | undefined
function onKey(event: KeyboardEvent) {
  const action = shortcutFor(event)
  if (!action || dialogOpen()) return
  if (event.repeat && !['nudge', 'undo', 'redo'].includes(action.type)) return
  if (action.type === 'save') {
    // Saving also works from inside the inspector's fields.
    event.preventDefault()
    void save()
    return
  }
  if (isTypingTarget(event.target) || !inEditor(event.target) || picker.value || menu.value) return
  switch (action.type) {
    case 'undo':
    case 'redo':
      event.preventDefault()
      history[action.type]()
      break
    case 'copy':
    case 'cut':
      if (hasTextSelection()) return
      event.preventDefault()
      editing[action.type]()
      break
    case 'paste':
      // The paste event that follows carries the system clipboard (steps copied in another tab);
      // if the browser sends none, paste what was copied in this tab.
      clearTimeout(pasteFallback)
      pasteFallback = setTimeout(() => editing.paste(pasteAnchor()), 60)
      break
    case 'duplicate':
      event.preventDefault()
      editing.duplicate()
      break
    case 'select-all':
      event.preventDefault()
      editing.selectAll()
      break
    case 'delete':
      if (!editing.selectedIds().length && !flow.getSelectedEdges.value.length) return
      event.preventDefault()
      editing.remove()
      break
    case 'escape':
      if (helpOpen.value) helpOpen.value = false
      else {
        editing.clearSelection()
        selectedId.value = null
        infoOpen.value = false
      }
      break
    case 'help':
      event.preventDefault()
      helpOpen.value = !helpOpen.value
      break
    case 'add-step':
      event.preventDefault()
      openAddStep()
      break
    case 'fit':
      event.preventDefault()
      fitView({ ...FIT_VIEW, duration: 300 })
      break
    case 'layout':
      event.preventDefault()
      editing.tidy()
      break
    case 'nudge':
      // Stops Vue Flow's own arrow handling on a focused step, so it moves only once.
      if (editing.nudge(action.dx, action.dy)) {
        event.preventDefault()
        event.stopPropagation()
      }
      break
  }
}
function onPaste(event: ClipboardEvent) {
  if (dialogOpen() || isTypingTarget(event.target) || !inEditor(event.target) || picker.value) return
  clearTimeout(pasteFallback)
  event.preventDefault()
  const at = pasteAnchor()
  if (!editing.pasteText(event.clipboardData?.getData('text/plain') ?? '', at)) editing.paste(at)
}

// ---- Right-click menus ----
interface CanvasMenuState {
  kind: 'node' | 'pane' | 'edge'
  ids: string[]
  edgeId?: string
  /** Pixels inside the canvas, and the same point in flow coordinates. */
  x: number
  y: number
  at: Point
}
const menu = ref<CanvasMenuState | null>(null)
function openMenu(kind: CanvasMenuState['kind'], event: MouseEvent, ids: string[] = [], edgeId?: string) {
  event.preventDefault()
  const box = stage.value?.getBoundingClientRect()
  if (!box) return
  picker.value = null
  helpOpen.value = false
  menu.value = {
    kind,
    ids,
    edgeId,
    x: event.clientX - box.left,
    y: event.clientY - box.top,
    at: flowPoint({ x: event.clientX, y: event.clientY }),
  }
}
flow.onNodeContextMenu(({ event, node }) => {
  const ids = node.selected ? editing.selectedIds() : [node.id]
  if (!node.selected) editing.selectOnly([node.id])
  openMenu('node', event as MouseEvent, ids)
})
flow.onSelectionContextMenu(({ event, nodes: chosen }) =>
  openMenu(
    'node',
    event,
    chosen.map((node) => node.id),
  ),
)
flow.onPaneContextMenu((event) => openMenu('pane', event))
flow.onEdgeContextMenu(({ event, edge }) => openMenu('edge', event as MouseEvent, [], edge.id))
const menuItems = computed<MenuItem[]>(() => {
  const current = menu.value
  if (!current) return []
  if (current.kind === 'pane')
    return [
      { key: 'paste', label: 'Dán ở đây', icon: ClipboardPaste, shortcut: `${mod}+V` },
      { key: 'add', label: 'Thêm bước…', icon: Plus, shortcut: 'N' },
      { key: 'select-all', label: 'Chọn tất cả', icon: BoxSelect, shortcut: `${mod}+A` },
      { key: 'tidy', label: 'Sắp xếp tự động', icon: Network, shortcut: 'Shift+L', divided: true },
      { key: 'fit', label: 'Vừa màn hình', icon: Maximize, shortcut: 'Shift+1' },
    ]
  if (current.kind === 'edge')
    return [
      { key: 'insert', label: 'Chèn bước vào đây…', icon: Plus },
      { key: 'remove-edge', label: 'Xóa đường nối', icon: Trash2, shortcut: 'Delete', danger: true, divided: true },
    ]
  const onlyTrigger = current.ids.every((id) => nodes.value.find((node) => node.id === id)?.data?.kind === 'trigger')
  const reason = 'Mỗi luồng chỉ có một bước kích hoạt'
  const many = current.ids.length > 1 ? ` ${current.ids.length} bước` : ''
  return [
    { key: 'copy', label: `Sao chép${many}`, icon: Copy, shortcut: `${mod}+C`, disabled: onlyTrigger, reason },
    { key: 'cut', label: `Cắt${many}`, icon: Scissors, shortcut: `${mod}+X`, disabled: onlyTrigger, reason },
    { key: 'duplicate', label: 'Nhân bản', icon: CopyPlus, shortcut: `${mod}+D`, disabled: onlyTrigger, reason },
    { key: 'disconnect', label: 'Ngắt kết nối', icon: Unlink },
    {
      key: 'delete',
      label: `Xóa${many}`,
      icon: Trash2,
      shortcut: 'Delete',
      danger: true,
      divided: true,
      disabled: onlyTrigger,
      reason,
    },
  ]
})
async function runMenu(key: string) {
  const current = menu.value
  menu.value = null
  if (!current) return
  const box = stage.value?.getBoundingClientRect()
  const client = { x: current.x + (box?.left ?? 0), y: current.y + (box?.top ?? 0) }
  switch (key) {
    case 'paste': {
      // Copied in another tab: only the system clipboard has it, read on this explicit request.
      const clip = editing.hasClip.value ? null : await editing.readClipboard()
      editing.paste(current.at, clip ?? undefined)
      break
    }
    case 'add':
      openPicker({ mode: 'free', at: current.at }, client)
      break
    case 'select-all':
      editing.selectAll()
      break
    case 'tidy':
      editing.tidy()
      break
    case 'fit':
      fitView({ ...FIT_VIEW, duration: 300 })
      break
    case 'insert':
      if (current.edgeId) insertOnEdge(current.edgeId, client)
      break
    case 'remove-edge':
      clearOverlay()
      edges.value = edges.value.filter((edge) => edge.id !== current.edgeId)
      notify('Đã xóa đường nối.', true)
      break
    case 'copy':
      editing.copy(current.ids)
      break
    case 'cut':
    case 'duplicate':
      editing.selectOnly(current.ids)
      await nextTick()
      editing[key]()
      break
    case 'disconnect':
      editing.disconnect(current.ids)
      break
    case 'delete':
      editing.remove(current.ids)
      break
  }
}

// ---- Canvas preferences, kept per browser ----
function preference(key: string, fallback: boolean) {
  try {
    const value = localStorage.getItem(`dx.flow.${key}`)
    return value === null ? fallback : value === '1'
  } catch {
    return fallback
  }
}
const snapToGrid = ref(preference('snap', true))
const showMinimap = ref(preference('minimap', true))
watch([snapToGrid, showMinimap], ([snap, minimap]) => {
  try {
    localStorage.setItem('dx.flow.snap', snap ? '1' : '0')
    localStorage.setItem('dx.flow.minimap', minimap ? '1' : '0')
  } catch {
    // Private windows may refuse storage; the toggle still works for this visit.
  }
})
// The viewport object is replaced on every pan/zoom frame; the template reads only these
// derived values, so panning does not re-render the whole editor.
const zoomPercent = computed(() => Math.round(viewport.value.zoom * 100))
const MIN_ZOOM = 0.3
const MAX_ZOOM = 1.6
const atMinZoom = computed(() => viewport.value.zoom <= MIN_ZOOM + 0.001)
const atMaxZoom = computed(() => viewport.value.zoom >= MAX_ZOOM - 0.001)
// Props for Vue Flow and the minimap that must keep their identity: Vue Flow copies a changed
// option into its store (and the minimap redraws) whenever a new object/function arrives.
const EDGE_OPTIONS = { type: 'smoothstep' } as const
const SNAP_GRID: [number, number] = [20, 20]
const miniMapColor = (node: Node<FlowNodeData>) => KINDS[node.data!.kind].color

/** The inspector takes room from the canvas; pan so the step being edited stays in sight. */
function ensureVisible(id: string) {
  const node = flow.findNode(id)
  if (!node) return
  const { x, y, zoom } = viewport.value
  const { width, height } = dimensions.value
  if (!width || !height) return
  const left = node.computedPosition.x * zoom + x
  const top = node.computedPosition.y * zoom + y
  // Branch tags stick out to the right of a step.
  const right = left + ((node.dimensions.width || 250) + 70) * zoom
  const bottom = top + (node.dimensions.height || 80) * zoom
  const pad = 24
  const dx = left < pad ? pad - left : right > width - pad ? Math.max(width - pad - right, pad - left) : 0
  const dy = top < pad ? pad - top : bottom > height - pad ? Math.max(height - pad - bottom, pad - top) : 0
  if (dx || dy) void flow.setViewport({ x: x + dx, y: y + dy, zoom }, { duration: 250 })
}
// Waits for the inspector to slide in; only the latest choice pans, and never after leaving.
let revealTimer: ReturnType<typeof setTimeout> | undefined
watch(selectedId, (id) => {
  clearTimeout(revealTimer)
  if (id) revealTimer = setTimeout(() => ensureVisible(id), 240)
})


// ---- Live validation ----
const errors = ref<{ node_id: string | null; message: string }[]>([])
let validateTimer: ReturnType<typeof setTimeout> | undefined
// Same JSON as undo and "unsaved" use: one serialisation per change, none while dragging.
watch(editing.graphJson, () => {
  clearTimeout(validateTimer)
  validateTimer = setTimeout(validate, 500)
})
async function validate() {
  if (!nodes.value.length) return
  try {
    const result = await api.request<{ errors: { node_id: string | null; message: string }[] }>(
      '/automations/validate',
      { method: 'POST', body: JSON.stringify(toApi(nodes.value, edges.value)) },
    )
    errors.value = result.errors
    for (const node of nodes.value) {
      const mine = result.errors.filter((e) => e.node_id === node.id).map((e) => e.message)
      if (JSON.stringify(mine) !== JSON.stringify(node.data?.errors ?? []))
        node.data = { ...node.data!, errors: mine }
    }
  } catch {
    // Validation is advisory while drawing; saving validates again on the server.
  }
}
const generalErrors = computed(() => errors.value.filter((e) => !e.node_id))
function focusNode(id: string | null) {
  if (!id) return
  selectedId.value = id
  editing.selectOnly([id])
  fitView({ nodes: [id], padding: 1.2, maxZoom: 1.1, duration: 300 })
}
/** Steps with problems, in canvas order; the header chip walks through them one by one. */
const issueNodes = computed(() => [
  ...new Set(errors.value.map((item) => item.node_id).filter((id): id is string => !!id)),
])
let issueCursor = 0
function nextIssue() {
  if (!issueNodes.value.length) {
    // Only flow-wide problems: they are listed in the flow's info panel.
    selectedId.value = null
    infoOpen.value = true
    return
  }
  focusNode(issueNodes.value[issueCursor % issueNodes.value.length]!)
  issueCursor += 1
}

// ---- Test runs and recorded runs painted on the canvas ----
const overlay = ref(false)
const overlayTitle = ref('')
function paint(steps: Step[], title: string) {
  const painted = paintRun(nodes.value, edges.value, steps)
  nodes.value = painted.nodes
  edges.value = painted.edges
  overlay.value = true
  overlayTitle.value = title
}
function clearOverlay() {
  if (!overlay.value) return
  overlay.value = false
  for (const node of nodes.value)
    if (node.data?.status || node.data?.outcome)
      node.data = { ...node.data, status: undefined, branch: undefined, message: undefined, people: undefined, outcome: undefined }
  edges.value = edges.value.map((edge) => ({
    ...edge,
    animated: false,
    class: edge.sourceHandle ? `edge-${tone(edge.sourceHandle)}` : undefined,
  }))
}
const drawer = ref<'test' | 'runs' | null>(null)
const sample = ref('')
/** Process samples also carry the form's answers and the decision each person takes. */
function processSample() {
  const decisions = Object.fromEntries(
    nodes.value
      .filter((node) => outputs(node.data!.kind, node.data!.config).length && node.data!.kind !== 'if')
      .map((node) => [node.id, outputs(node.data!.kind, node.data!.config)[0]]),
  )
  const answers = Object.fromEntries(Object.keys(processForm.value?.fields ?? {}).map((key) => [key.slice(5), null]))
  return { ...(trigger.value?.sample ?? {}), form: answers, decisions }
}
watch(
  () => [trigger.value?.key, processForm.value?.id, catalog.data.value ? 1 : 0],
  () => {
    sample.value = JSON.stringify(isProcess.value ? processSample() : (trigger.value?.sample ?? {}), null, 2)
  },
  { immediate: true },
)
const testResult = ref<{ valid: boolean; matched?: boolean; steps: Step[]; outcome?: string | null } | null>(null)
const testing = ref(false)
async function runTest() {
  error.value = null
  let data: Record<string, unknown>
  try {
    data = JSON.parse(sample.value || '{}')
  } catch {
    error.value = new Error('Dữ liệu mẫu chưa đúng định dạng JSON.')
    return
  }
  busy.value = true
  testing.value = true
  try {
    testResult.value = await api.request('/automations/test', {
      method: 'POST',
      body: JSON.stringify({ graph: toApi(nodes.value, edges.value), data }),
    })
    if (testResult.value?.valid) paint(testResult.value.steps, 'Kết quả chạy thử (không tác động thật)')
  } catch (cause) {
    error.value = cause
  } finally {
    busy.value = false
    testing.value = false
  }
}
const runs = useQuery({
  queryKey: computed(() => ['automation-runs', ruleId.value]),
  queryFn: () => api.request<Page<Run>>(`/automations/${ruleId.value}/runs`),
  enabled: computed(() => !!ruleId.value && drawer.value === 'runs'),
  refetchInterval: 10_000,
})
const activeRun = ref<string | null>(null)
function showRun(run: Run) {
  activeRun.value = run.id
  paint(
    run.steps,
    `Lượt chạy ${formatDate(run.created_at, true)}${run.subject ? ` · ${run.subject.title}` : ''}`,
  )
}

// ---- Run now, for real, with an existing record ----
const family = computed(() => (trigger.value?.key ?? '').split('.')[0] as 'task' | 'case' | 'post')
const familyLabel = computed(
  () => ({ task: 'công việc', case: 'hồ sơ', post: 'bài viết' })[family.value] ?? 'bản ghi',
)
const runDialog = ref(false)
const pickQuery = ref('')
// One search per pause in typing, not one request per key.
const pickSearch = useDebounced(pickQuery, 250)
const pickId = ref('')
const candidates = useQuery({
  queryKey: computed(() => ['automation-candidates', ruleId.value, pickSearch.value]),
  queryFn: () =>
    api.request<{ items: { id: string; title: string; status: string | null }[] }>(
      `/automations/${ruleId.value}/candidates?q=${encodeURIComponent(pickSearch.value)}`,
    ),
  enabled: computed(() => runDialog.value && !!ruleId.value),
})
function openRunDialog() {
  pickId.value = ''
  pickQuery.value = ''
  pickSearch.value = ''
  runDialog.value = true
}
async function runNow() {
  busy.value = true
  error.value = null
  try {
    const run = await api.request<Run>(`/automations/${ruleId.value}/run`, {
      method: 'POST',
      body: JSON.stringify({ ref_id: pickId.value }),
    })
    runDialog.value = false
    drawer.value = 'runs'
    await runs.refetch()
    showRun(run)
    notice.value =
      run.state === 'not_matched'
        ? 'Đã chạy: dữ liệu không thỏa điều kiện nên không hành động nào thực hiện.'
        : 'Đã chạy thật — xem kết quả từng bước trên canvas.'
    await queryClient.invalidateQueries({ queryKey: ['automations'] })
  } catch (cause) {
    error.value = cause
  } finally {
    busy.value = false
  }
}

// ---- Save / enable ----
const saving = ref(false)
/** Saves the draft; resolves true when it is stored, so publishing can follow. */
async function save(): Promise<boolean> {
  if (busy.value) return false
  saving.value = true
  busy.value = true
  error.value = null
  clearOverlay()
  try {
    const body = {
      name: name.value,
      description: description.value,
      graph: toApi(nodes.value, edges.value),
      scope: attachable.value ? scope.value : 'all',
    }
    const rule = ruleId.value
      ? await api.request<Rule>(`/automations/${ruleId.value}`, {
          method: 'PUT',
          body: JSON.stringify({ ...body, expected_revision: revision.value }),
        })
      : await api.request<Rule>('/automations', { method: 'POST', body: JSON.stringify(body) })
    revision.value = rule.revision
    enabled.value = rule.enabled
    saved.value = snapshot()
    notice.value = 'Đã lưu luồng.'
    await queryClient.invalidateQueries({ queryKey: ['automations'] })
    if (!ruleId.value) {
      ruleId.value = rule.id
      await router.replace(`/processes/${rule.id}`)
    }
    return true
  } catch (cause) {
    error.value = cause
    return false
  } finally {
    busy.value = false
    saving.value = false
  }
}
/** Publishing happens in its own dialog; the top bar only has to keep up with the result. */
function processChanged(rule: Pick<Rule, 'revision' | 'active_version_no'> & { active_version_id: string | null }) {
  revision.value = rule.revision
  enabled.value = !!rule.active_version_id
  activeVersion.value = rule.active_version_no ?? null
}
const formDetails = useQuery({
  queryKey: ['forms'],
  queryFn: () => api.request<Page<FormTemplate>>('/forms'),
  enabled: isProcess,
})
const processFormDetail = computed(() =>
  formDetails.data.value?.items.find((form) => form.id === processForm.value?.id),
)
/** A changed form is a new form: the draft's trigger moves to it and saving keeps that. */
async function formRevised(formId: string) {
  editingForm.value = false
  await Promise.all([catalog.refetch(), formDetails.refetch()])
  const start = triggerNode.value
  if (start?.data) start.data = { ...start.data, config: { ...start.data.config, form_id: formId } }
  notice.value = 'Đã tạo biểu mẫu mới và gắn vào bản nháp. Bấm Lưu để giữ thay đổi.'
}
// Capture phase: runs before Vue Flow's handlers, so arrow keys move a focused step only once.
onMounted(() => {
  window.addEventListener('keydown', onKey, true)
  document.addEventListener('paste', onPaste)
})
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKey, true)
  document.removeEventListener('paste', onPaste)
  clearTimeout(validateTimer)
  clearTimeout(noticeTimer)
  clearTimeout(pasteFallback)
  clearTimeout(revealTimer)
})
// Messages set directly (save, run) fade like the ones from notify().
watch(notice, (value) => {
  if (!value) return
  clearTimeout(noticeTimer)
  noticeTimer = setTimeout(() => (notice.value = ''), noticeUndo.value ? 6000 : 2800)
})
useUnsavedGuard(dirty)

provide(FLOW_CONTEXT, { triggers, userName, overlay, addAfter, insertOnEdge, hoveredEdge, forms })
const ai = useAi()
const offeredKinds = computed(() =>
  paletteKinds().filter((kind) => !['ai', 'ai_extract'].includes(kind) || ai.on('automation_ai')),
)
// A long list of step kinds: find one by name or purpose, and fold the groups you do not need.
const paletteQuery = ref('')
const foldedGroups = ref<string[]>([])
const palette = computed(() => {
  const needle = fold(paletteQuery.value.trim())
  return (['Bước cần người', 'Logic', 'Hành động', 'Dữ liệu và tài liệu'] as const)
    .map((group) => ({
      group,
      kinds: offeredKinds.value.filter(
        (kind) =>
          KINDS[kind].group === group && (!needle || fold(`${KINDS[kind].title} ${KINDS[kind].hint}`).includes(needle)),
      ),
    }))
    .filter((section) => section.kinds.length)
})
function toggleGroup(group: string) {
  foldedGroups.value = foldedGroups.value.includes(group)
    ? foldedGroups.value.filter((item) => item !== group)
    : [...foldedGroups.value, group]
}
</script>
<template>
  <div ref="root" class="flow-editor">
    <header class="flow-topbar">
      <RouterLink
        :to="isProcess ? '/processes' : '/processes?tab=automation'"
        class="icon-button"
        aria-label="Về danh sách"
        ><ArrowLeft :size="18"
      /></RouterLink>
      <h1 class="sr-only">{{ name }}</h1>
      <input v-model="name" class="flow-name" aria-label="Tên luồng" maxlength="200" />
      <span v-if="dirty" class="tag">Chưa lưu</span>
      <button
        v-if="errors.length"
        type="button"
        class="flow-issues"
        :title="`${errors.map((e) => e.message).join('\n')}\n\nBấm để lần lượt tới từng bước có vấn đề.`"
        :aria-label="`${errors.length} vấn đề cần xử lý. Bấm để tới bước có vấn đề tiếp theo.`"
        @click="nextIssue"
      >
        <AlertTriangle :size="15" aria-hidden="true" />{{ errors.length }} vấn đề
      </button>
      <span v-else-if="nodes.length > 1" class="flow-ok" title="Hợp lệ"><CheckCircle2 :size="15" aria-hidden="true" /><span class="btn-label wide-label">Hợp lệ</span></span>
      <button
        class="icon-button"
        :class="{ active: infoOpen }"
        :aria-pressed="infoOpen"
        aria-label="Thông tin luồng và hướng dẫn"
        title="Thông tin luồng và hướng dẫn"
        @click="
          () => {
            selectedId = null
            infoOpen = !infoOpen
          }
        "
      >
        <Info :size="17" />
      </button>
      <div class="flow-topbar-actions">
        <span v-if="ruleId" class="tag">{{
          activeVersion ? `Phiên bản ${activeVersion}` : 'Bản nháp'
        }}</span>
        <button
          class="button secondary small"
          aria-label="Phát hành"
          :disabled="!ruleId"
          :title="ruleId ? 'Phân quyền, kịch bản thử và phát hành' : 'Lưu luồng lần đầu trước khi phát hành'"
          @click="panelOpen = true"
        >
          <Rocket :size="15" /><span class="btn-label">Phát hành</span>
        </button>
        <button
          v-if="isProcess && processFormDetail"
          class="button secondary small"
          aria-label="Sửa biểu mẫu"
          title="Sửa biểu mẫu"
          @click="editingForm = true"
        >
          <FilePen :size="15" /><span class="btn-label wide-label">Sửa biểu mẫu</span>
        </button>
        <button
          class="button secondary small"
          :class="{ active: drawer === 'test' }"
          :aria-pressed="drawer === 'test'"
          aria-label="Chạy thử"
          title="Chạy với dữ liệu mẫu, không tác động thật"
          @click="drawer = drawer === 'test' ? null : 'test'"
        >
          <FlaskConical :size="15" /><span class="btn-label">Chạy thử</span>
        </button>
        <button
          class="button secondary small"
          :disabled="!ruleId"
          :class="{ active: drawer === 'runs' }"
          :aria-pressed="drawer === 'runs'"
          aria-label="Lịch sử chạy"
          :title="ruleId ? 'Các lần luồng đã chạy' : 'Lưu luồng trước để xem lịch sử chạy'"
          @click="drawer = drawer === 'runs' ? null : 'runs'"
        >
          <History :size="15" /><span class="btn-label wide-label">Lịch sử chạy</span>
        </button>
        <button
          class="button small"
          :class="{ secondary: !dirty && !!ruleId }"
          :disabled="busy || (!dirty && !!ruleId)"
          :aria-busy="saving"
          :aria-label="saving ? 'Đang lưu…' : !dirty && ruleId ? 'Đã lưu' : 'Lưu'"
          :title="saving ? 'Đang lưu…' : busy ? 'Đợi thao tác đang chạy xong' : !dirty && !!ruleId ? 'Không có thay đổi cần lưu' : `Lưu (${mod}+S)`"
          @click="save"
        >
          <component :is="!dirty && !!ruleId && !saving ? CheckCircle2 : Save" :size="15" /><span class="btn-label">{{
            saving ? 'Đang lưu…' : !dirty && ruleId ? 'Đã lưu' : 'Lưu'
          }}</span>
        </button>
      </div>
    </header>
    <div v-if="!statusClosed" class="flow-status" :class="{ on: enabled && ruleId, off: !enabled || !ruleId }">
      <Zap v-if="enabled && ruleId" :size="16" /><Power v-else :size="16" />
      <template v-if="isProcess">
        <span v-if="!ruleId"
          >Quy trình mới chưa lưu. Chọn biểu mẫu ở node kích hoạt, cấu hình từng bước, lưu rồi bấm <b>Phát hành</b>.</span
        >
        <span v-else-if="enabled"
          >Đang áp dụng phiên bản {{ activeVersion }} cho biểu mẫu <b>“{{ processForm?.name }}”</b>. Canvas là bản nháp: chỉnh
          sửa không ảnh hưởng ai cho đến khi phát hành lại.</span
        >
        <span v-else
          >Bản nháp, chưa ai dùng được. Bấm <b>Phát hành</b> để phân quyền, chạy kịch bản thử và đưa vào áp dụng.</span
        >
      </template>
      <span v-else-if="!ruleId"
        >Luồng mới chưa lưu. Lưu → <b>Chạy thử</b> với dữ liệu mẫu → <b>Phát hành</b> để luồng
        <b>tự chạy</b> mỗi khi “{{ trigger?.label ?? 'sự kiện' }}”.</span
      >
      <span v-else-if="enabled && attachedMode"
        >Đang bật cho <b>công việc được gắn</b>: nhân viên tự gắn luồng vào việc của mình (hiện có
        {{ attachedCount }} việc); mỗi khi <b>{{ trigger?.label }}</b> ở những việc đó, luồng tự chạy.</span
      >
      <span v-else-if="enabled"
        >Đang tự chạy: mỗi khi <b>{{ trigger?.label ?? 'sự kiện' }}</b> ở bất kỳ {{ familyLabel }} nào, hệ thống tự
        chạy luồng này — không cần bấm nút.</span
      >
      <span v-else
        >Bản nháp: khi <b>{{ trigger?.label ?? 'sự kiện' }}</b> luồng <b>không</b> tự chạy. Bấm <b>Phát hành</b>
        để áp dụng, hoặc chạy ngay với một {{ familyLabel }} có sẵn.</span
      >
      <label v-if="attachable && !isProcess" class="scope-select"
        >Áp dụng cho
        <select v-model="scope" aria-label="Phạm vi áp dụng">
          <option value="all">Mọi công việc</option>
          <option value="attached">Chỉ công việc được gắn</option>
        </select></label
      >
      <button
        v-if="ruleId && !isProcess"
        class="button secondary small"
        :disabled="dirty || busy"
        :title="dirty ? 'Lưu thay đổi trước khi chạy' : ''"
        @click="openRunDialog"
      >
        <PlayCircle :size="15" />Chạy ngay với {{ familyLabel }}…
      </button>
      <button class="icon-button status-close" aria-label="Ẩn dòng thông báo" title="Ẩn" @click="statusClosed = true">
        <X :size="15" />
      </button>
    </div>
    <div v-if="error" class="notice error flow-alert" role="alert">
      <span>{{ errorText(error) }}</span
      ><button v-if="error instanceof ApiError && error.status === 409" class="button secondary small" @click="router.go(0)">
        Tải bản mới</button
      ><button class="icon-button" aria-label="Đóng thông báo lỗi" title="Đóng" @click="error = null"><X :size="15" /></button>
    </div>
    <div class="flow-body" :class="{ inspecting: !!selected?.data || infoOpen }">
      <aside class="flow-palette" aria-label="Các loại bước">
        <label class="search-box palette-search"
          ><Search :size="15" /><input
            v-model="paletteQuery"
            type="search"
            placeholder="Tìm bước…"
            aria-label="Tìm loại bước"
        /></label>
        <p class="muted">Kéo thả vào canvas hoặc bấm để thêm sau bước đang chọn.</p>
        <p v-if="!palette.length && !pluginQuery.length" class="muted">Không có bước nào khớp “{{ paletteQuery }}”.</p>
        <div v-for="section in palette" :key="section.group" class="palette-group">
          <button
            type="button"
            class="palette-group-head"
            :aria-expanded="!!paletteQuery || !foldedGroups.includes(section.group)"
            @click="toggleGroup(section.group)"
          >
            <ChevronDown
              :size="14"
              :class="{ folded: !paletteQuery && foldedGroups.includes(section.group) }"
            /><span class="section-label">{{ section.group }}</span
            ><small class="muted">{{ section.kinds.length }}</small>
          </button>
          <template v-if="paletteQuery || !foldedGroups.includes(section.group)">
          <button
            v-for="kind in section.kinds"
            :key="kind"
            class="palette-item"
            draggable="true"
            :disabled="kind === 'trigger' && !!triggerNode"
            :style="{ '--node-color': KINDS[kind].color }"
            @dragstart="onDragStart($event, kind)"
            @click="addFromPalette(kind)"
          >
            <span class="flow-node-icon small"><component :is="KINDS[kind].icon" :size="16" /></span>
            <span class="grow"
              ><strong>{{ KINDS[kind].title }}</strong><small>{{ KINDS[kind].hint }}</small></span
            >
          </button>
          </template>
        </div>
        <div v-if="pluginQuery.length" class="palette-group">
          <button
            type="button"
            class="palette-group-head"
            :aria-expanded="!!paletteQuery || !foldedGroups.includes('Plugin')"
            @click="toggleGroup('Plugin')"
          >
            <ChevronDown :size="14" :class="{ folded: !paletteQuery && foldedGroups.includes('Plugin') }" /><span
              class="section-label"
              >Plugin</span
            ><small class="muted">{{ pluginQuery.length }}</small>
          </button>
          <template v-if="paletteQuery || !foldedGroups.includes('Plugin')">
            <button
              v-for="step in pluginQuery"
              :key="`${step.plugin_id}:${step.kind}`"
              class="palette-item"
              draggable="true"
              :style="{ '--node-color': KINDS.plugin_action.color }"
              @dragstart="onPluginDragStart($event, step)"
              @click="addPluginStep(step)"
            >
              <span class="flow-node-icon small"><component :is="KINDS.plugin_action.icon" :size="16" /></span>
              <span class="grow"
                ><strong>{{ step.title }}</strong><small>{{ step.plugin_name }}</small></span
              >
            </button>
          </template>
        </div>
      </aside>
      <section class="flow-canvas">
        <div
          ref="stage"
          class="flow-stage"
          @drop.prevent="onDrop"
          @dragover.prevent
          @pointermove="pointer = { x: $event.clientX, y: $event.clientY }"
          @pointerleave="pointer = null"
        >
          <VueFlow
            v-model:nodes="nodes"
            v-model:edges="edges"
            :is-valid-connection="isValidConnection"
            :default-edge-options="EDGE_OPTIONS"
            :delete-key-code="null"
            :snap-to-grid="snapToGrid"
            :snap-grid="SNAP_GRID"
            :min-zoom="MIN_ZOOM"
            :max-zoom="MAX_ZOOM"
            :connection-radius="30"
            fit-view-on-init
          >
            <template #node-flow="nodeProps"><FlowNode v-bind="nodeProps" /></template>
            <template #edge-smoothstep="edgeProps"><FlowEdge v-bind="edgeProps" /></template>
            <template #edge-default="edgeProps"><FlowEdge v-bind="edgeProps" curve="bezier" /></template>
            <Background :gap="20" :size="1.4" pattern-color="#c5d3de" />
            <MiniMap
              v-if="showMinimap"
              position="bottom-right"
              pannable
              zoomable
              :width="180"
              :height="120"
              aria-label="Bản đồ thu nhỏ của luồng"
              :node-color="miniMapColor"
              :node-stroke-width="0"
            />
          </VueFlow>

          <div class="canvas-top">
            <div v-if="overlay" class="flow-overlay-bar">
              <Play :size="14" aria-hidden="true" /><span>{{ overlayTitle }}</span>
              <button class="button ghost small" @click="clearOverlay">Ẩn kết quả</button>
            </div>
            <div
              v-if="editing.selectedNodes.value.length > 1"
              class="selection-bar"
              role="toolbar"
              aria-label="Thao tác với các bước đã chọn"
            >
              <strong>{{ editing.selectedNodes.value.length }} bước đã chọn</strong>
              <span class="toolbar-divider" aria-hidden="true" />
              <button class="icon-button" aria-label="Căn thẳng mép trái" title="Căn thẳng mép trái" @click="editing.align('left')">
                <AlignStartVertical :size="16" />
              </button>
              <button
                class="icon-button"
                aria-label="Căn thẳng hàng ngang"
                title="Căn thẳng hàng ngang"
                @click="editing.align('middle')"
              >
                <AlignCenterHorizontal :size="16" />
              </button>
              <button
                class="icon-button"
                aria-label="Dàn đều theo chiều ngang"
                :title="editing.selectedNodes.value.length < 3 ? 'Chọn từ 3 bước để dàn đều' : 'Dàn đều theo chiều ngang'"
                :disabled="editing.selectedNodes.value.length < 3"
                @click="editing.align('distribute-h')"
              >
                <AlignHorizontalDistributeCenter :size="16" />
              </button>
              <button
                class="icon-button"
                aria-label="Dàn đều theo chiều dọc"
                :title="editing.selectedNodes.value.length < 3 ? 'Chọn từ 3 bước để dàn đều' : 'Dàn đều theo chiều dọc'"
                :disabled="editing.selectedNodes.value.length < 3"
                @click="editing.align('distribute-v')"
              >
                <AlignVerticalDistributeCenter :size="16" />
              </button>
              <span class="toolbar-divider" aria-hidden="true" />
              <button class="icon-button" aria-label="Sao chép" :title="`Sao chép (${mod}+C)`" @click="editing.copy()">
                <Copy :size="16" />
              </button>
              <button class="icon-button" aria-label="Nhân bản" :title="`Nhân bản (${mod}+D)`" @click="editing.duplicate()">
                <CopyPlus :size="16" />
              </button>
              <button class="icon-button danger" aria-label="Xóa các bước đã chọn" title="Xóa (Delete)" @click="editing.remove()">
                <Trash2 :size="16" />
              </button>
              <button class="icon-button" aria-label="Bỏ chọn" title="Bỏ chọn (Esc)" @click="editing.clearSelection()">
                <X :size="16" />
              </button>
            </div>
            <div v-if="generalErrors.length" class="flow-general-errors" role="alert">
              <AlertTriangle :size="15" aria-hidden="true" />
              <span>{{ generalErrors.map((e) => e.message).join(' · ') }}</span>
            </div>
            <div v-if="notice" class="flow-toast" role="status" aria-live="polite">
              <span>{{ notice }}</span>
              <button v-if="noticeUndo" type="button" class="button ghost small" @click="history.undo()">
                <Undo2 :size="14" />Hoàn tác
              </button>
            </div>
          </div>

          <div class="canvas-toolbar" role="toolbar" aria-label="Công cụ canvas">
            <button
              class="icon-button"
              aria-label="Thu nhỏ"
              title="Thu nhỏ"
              :disabled="atMinZoom"
              @click="flow.zoomOut({ duration: 150 })"
            >
              <ZoomOut :size="16" />
            </button>
            <button class="zoom-level" type="button" title="Về cỡ 100%" aria-label="Về cỡ 100%" @click="flow.zoomTo(1, { duration: 150 })">
              {{ zoomPercent }}%
            </button>
            <button
              class="icon-button"
              aria-label="Phóng to"
              title="Phóng to"
              :disabled="atMaxZoom"
              @click="flow.zoomIn({ duration: 150 })"
            >
              <ZoomIn :size="16" />
            </button>
            <button
              class="icon-button"
              aria-label="Vừa màn hình"
              title="Vừa màn hình (Shift+1)"
              @click="fitView({ ...FIT_VIEW, duration: 300 })"
            >
              <Maximize :size="16" />
            </button>
            <span class="toolbar-divider" aria-hidden="true" />
            <button
              class="icon-button"
              aria-label="Hoàn tác"
              :title="history.canUndo.value ? `Hoàn tác (${mod}+Z)` : 'Chưa có thao tác nào để hoàn tác'"
              :disabled="!history.canUndo.value"
              @click="history.undo()"
            >
              <Undo2 :size="16" />
            </button>
            <button
              class="icon-button"
              aria-label="Làm lại"
              :title="history.canRedo.value ? `Làm lại (${mod}+Shift+Z)` : 'Không có thao tác nào để làm lại'"
              :disabled="!history.canRedo.value"
              @click="history.redo()"
            >
              <Redo2 :size="16" />
            </button>
            <span class="toolbar-divider" aria-hidden="true" />
            <button
              class="icon-button"
              aria-label="Sắp xếp tự động"
              title="Sắp xếp tự động từ trái sang phải (Shift+L)"
              :disabled="nodes.length < 2"
              @click="editing.tidy()"
            >
              <Network :size="16" />
            </button>
            <button
              class="icon-button desk-only"
              :class="{ active: snapToGrid }"
              :aria-pressed="snapToGrid"
              aria-label="Bám lưới khi kéo"
              :title="snapToGrid ? 'Đang bám lưới khi kéo: bấm để tắt' : 'Bám lưới khi kéo: bấm để bật'"
              @click="snapToGrid = !snapToGrid"
            >
              <Grid3x3 :size="16" />
            </button>
            <button
              class="icon-button desk-only"
              :class="{ active: showMinimap }"
              :aria-pressed="showMinimap"
              aria-label="Bản đồ thu nhỏ"
              :title="showMinimap ? 'Ẩn bản đồ thu nhỏ' : 'Hiện bản đồ thu nhỏ'"
              @click="showMinimap = !showMinimap"
            >
              <MapIcon :size="16" />
            </button>
            <button
              class="icon-button desk-only"
              :class="{ active: helpOpen }"
              :aria-pressed="helpOpen"
              aria-label="Phím tắt"
              title="Phím tắt (?)"
              data-shortcut-toggle
              @click="helpOpen = !helpOpen"
            >
              <Keyboard :size="16" />
            </button>
          </div>

          <ShortcutHelp v-if="helpOpen" @close="helpOpen = false" />
          <StepPicker
            v-if="picker"
            :title="pickerTitle"
            :kinds="pickerKinds"
            :plugins="pluginSteps.data.value ?? []"
            :x="picker.x"
            :y="picker.y"
            @pick="pick"
            @plugin="(step) => pick('plugin_action', pluginStepConfig(step))"
            @close="picker = null"
          />
          <CanvasMenu
            v-if="menu"
            :x="menu.x"
            :y="menu.y"
            :items="menuItems"
            :label="menu.kind === 'pane' ? 'Thao tác trên canvas' : menu.kind === 'edge' ? 'Thao tác với đường nối' : 'Thao tác với bước'"
            @select="runMenu"
            @close="menu = null"
          />
        </div>
        <section v-if="drawer" class="flow-drawer">
          <header>
            <strong v-if="drawer === 'test'"><FlaskConical :size="15" /> Chạy thử với dữ liệu mẫu</strong>
            <strong v-else><History :size="15" /> Lịch sử chạy</strong>
            <button class="icon-button" aria-label="Đóng ngăn dưới" title="Đóng" @click="drawer = null">
              <PanelBottomClose :size="16" />
            </button>
          </header>
          <div v-if="drawer === 'test'" class="drawer-test">
            <div class="field">
              <label for="sample-data"
                >{{ isProcess ? 'Hồ sơ mẫu' : 'Dữ liệu sự kiện' }} “{{ trigger?.label ?? 'chưa chọn' }}” (JSON)</label
              ><textarea id="sample-data" v-model="sample" class="code-editor" spellcheck="false" />
              <small v-if="isProcess" class="muted"
                >Điền câu trả lời biểu mẫu vào <code>form</code>, số tệp vào <code>file_count</code>. Mục
                <code>decisions</code> chọn quyết định giả lập cho từng bước: <code>approve</code>, <code>return</code>,
                <code>reject</code> (Xin ý kiến: <code>approve</code> = đồng ý), <code>completed</code>/<code>cancelled</code>
                cho Giao việc.</small
              >
            </div>
            <div class="drawer-result">
              <button
                class="button"
                :disabled="busy"
                :aria-busy="testing"
                :title="busy && !testing ? 'Đợi thao tác đang chạy xong' : ''"
                @click="runTest"
              >
                <Play :size="15" />{{ testing ? 'Đang chạy thử…' : 'Chạy thử luồng' }}
              </button>
              <p class="muted">
                <Info :size="13" /> Chạy thử không gửi thông báo, không tạo việc, không gọi ra ngoài{{
                  isProcess ? ', không giao hồ sơ cho ai duyệt' : ''
                }}.
              </p>
              <template v-if="testResult">
                <p v-if="!testResult.valid" class="overdue-text">Luồng còn lỗi cấu hình, sửa các node được đánh dấu.</p>
                <p v-else-if="isProcess && testResult.outcome">
                  Hồ sơ mẫu kết thúc: <strong>{{ OUTCOMES[testResult.outcome] ?? testResult.outcome }}</strong>, xem đường sáng
                  trên canvas.
                </p>
                <p v-else-if="isProcess" class="overdue-text">
                  Hồ sơ mẫu dừng giữa chừng, chưa có kết quả. Xem node báo lỗi, hoặc nối thêm bước Kết thúc.
                </p>
                <p v-else-if="testResult.matched">Dữ liệu này đi qua <strong>{{ testResult.steps.length }}</strong> bước, xem đường sáng trên canvas.</p>
                <p v-else>Dữ liệu này <strong>không thỏa điều kiện</strong>; không hành động nào chạy.</p>
              </template>
            </div>
          </div>
          <div v-else class="drawer-runs">
            <StatePanel
              v-if="runs.isPending.value || runs.error.value"
              :loading="runs.isPending.value"
              :error="runs.error.value"
              compact
              @retry="runs.refetch()"
            />
            <p v-else-if="!runs.data.value?.items.length" class="muted">Luồng chưa chạy lần nào.</p>
            <div
              v-for="run in runs.data.value?.items"
              :key="run.id"
              class="run-item"
              role="button"
              tabindex="0"
              :class="{ active: activeRun === run.id }"
              @click="showRun(run)"
              @keydown.enter="showRun(run)"
            >
              <StatusBadge :status="run.state" />
              <span class="grow run-subject">
                <strong>{{ run.subject?.title || 'Sự kiện' }}</strong>
                <small
                  >{{ formatDate(run.created_at, true) }} ·
                  {{ run.manual_by ? `chạy tay bởi ${run.manual_by}` : 'tự chạy theo sự kiện' }}</small
                >
              </span>
              <RouterLink
                v-if="run.subject?.link"
                :to="run.subject.link"
                class="button ghost small"
                @click.stop
                >Mở {{ { task: 'công việc', case: 'hồ sơ', post: 'bài viết' }[run.subject.type] }}</RouterLink
              >
            </div>
          </div>
        </section>
      </section>
      <aside v-if="selected?.data || infoOpen" class="flow-inspector" aria-label="Bảng cấu hình">
        <button
          class="icon-button inspector-close"
          aria-label="Đóng bảng cấu hình"
          title="Đóng (Esc)"
          @click="
            () => {
              selectedId = null
              infoOpen = false
            }
          "
        >
          <X :size="16" />
        </button>
        <NodeInspector
          v-if="selected?.data"
          :id="selected.id"
          :key="selected.id"
          :data="selected.data"
          :triggers="triggers"
          :fields="fields"
          :users="users.data.value?.items ?? NONE"
          :departments="departments.data.value?.items ?? NONE"
          :connections="connections.data.value?.items ?? NONE"
          :webhooks-enabled="!!catalog.data.value?.webhooks_enabled"
          :process="isProcess"
          :forms="forms"
          :subprocesses="subprocesses"
          @patch="patch"
          @label="setLabel"
          @remove="removeSelected"
          @duplicate="duplicateSelected"
        />
        <div v-else class="inspector">
          <header class="inspector-head">
            <span class="flow-node-icon small" style="--node-color: var(--muted)"><Info :size="16" /></span>
            <div class="grow"><small>LUỒNG</small><strong>Thông tin và hướng dẫn</strong></div>
          </header>
          <div class="inspector-body">
            <div class="field">
              <label for="flow-desc">Mô tả luồng</label
              ><textarea id="flow-desc" v-model="description" rows="3" maxlength="2000" />
            </div>
            <div class="flow-help">
              <strong>Cách dùng</strong>
              <ul>
                <li>Kéo bước từ cột trái vào canvas, hoặc bấm <b>+</b> ở mép phải một bước (hay giữa một đường nối) để chèn bước mới.</li>
                <li>Kéo từ chấm tròn bên phải sang bước khác để nối. Bước <b>Điều kiện</b> có hai cổng Đúng/Sai.</li>
                <li>Bấm một bước để cấu hình. <kbd>Shift</kbd> + kéo để quét chọn nhiều bước, <kbd>{{ mod }}</kbd> + bấm để thêm/bớt.</li>
                <li>
                  <kbd>{{ mod }}</kbd> <kbd>C</kbd> / <kbd>X</kbd> / <kbd>V</kbd> sao chép, cắt, dán (dán tại con trỏ, kể cả sang luồng
                  khác); <kbd>{{ mod }}</kbd> <kbd>D</kbd> nhân bản; <kbd>Delete</kbd> xóa bước hoặc đường nối đang chọn.
                </li>
                <li><kbd>{{ mod }}</kbd> <kbd>Z</kbd> hoàn tác, <kbd>{{ mod }}</kbd> <kbd>Shift</kbd> <kbd>Z</kbd> làm lại; phím mũi tên dịch bước đang chọn.</li>
                <li>Chuột phải lên bước hoặc nền canvas để mở menu nhanh; <kbd>?</kbd> xem toàn bộ phím tắt.</li>
                <li><b>Chạy thử</b> tô sáng đường đi với dữ liệu mẫu, không tác động thật.</li>
                <li>Luồng mới ở trạng thái tắt; lưu rồi bật khi đã chạy thử.</li>
              </ul>
            </div>
            <div v-if="isProcess" class="flow-help">
              <strong>Quy trình hồ sơ</strong>
              <ul>
                <li><b>Duyệt</b> có ba cổng: Duyệt, Trả lại, Từ chối. Cổng để trống thì hồ sơ kết thúc đúng như tên cổng.</li>
                <li><b>Xin ý kiến</b> hỏi nhiều người cùng lúc; nối cổng Đồng ý / Không đồng ý tới bước tiếp theo.</li>
                <li><b>Giao việc và chờ</b> tạo việc gắn với hồ sơ, chỉ đi tiếp khi việc được nghiệm thu hoặc bị hủy.</li>
                <li><b>Điều kiện</b> đọc được câu trả lời biểu mẫu (<code>form.…</code>) và số/tên tài liệu đính kèm.</li>
                <li>Người tạo hồ sơ xem được hồ sơ đang ở bước nào ngay trên sơ đồ này, trong tab <b>Quy trình</b>.</li>
              </ul>
            </div>
            <div v-if="errors.length" class="flow-help">
              <strong>Cần xử lý</strong>
              <ul>
                <li v-for="(item, index) in errors" :key="index">
                  <a v-if="item.node_id" href="#" @click.prevent="focusNode(item.node_id)">{{ item.message }}</a>
                  <span v-else>{{ item.message }}</span>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </aside>
    </div>
    <ModalDialog v-if="runDialog" :title="`Chạy ngay với một ${familyLabel}`" @close="runDialog = false">
      <div class="stack">
        <p class="muted">
          Luồng chạy như thể “{{ trigger?.label }}” vừa xảy ra với {{ familyLabel }} bạn chọn — kể cả khi luồng đang tắt.
          Dùng để áp dụng cho {{ familyLabel }} đã có từ trước, hoặc thử trên dữ liệu thật.
        </p>
        <label class="search-box" style="min-width: 0"
          ><Search :size="16" /><input
            v-model="pickQuery"
            type="search"
            :placeholder="`Tìm ${familyLabel}…`"
            :aria-label="`Tìm ${familyLabel}`"
        /></label>
        <div class="run-pick-list" role="radiogroup" :aria-label="`Chọn ${familyLabel}`">
          <p v-if="candidates.isPending.value" class="muted">Đang tải…</p>
          <p v-else-if="!candidates.data.value?.items.length" class="muted">
            Không có {{ familyLabel }} nào bạn được xem khớp từ khóa.
          </p>
          <label v-for="item in candidates.data.value?.items" :key="item.id" class="run-pick" :class="{ active: pickId === item.id }">
            <input v-model="pickId" type="radio" name="run-pick" :value="item.id" />
            <span class="grow">{{ item.title }}</span>
            <StatusBadge v-if="item.status" :status="item.status" />
          </label>
        </div>
        <div class="notice warning">
          <AlertTriangle :size="18" /><span
            >Đây là <b>chạy thật</b>: thông báo được gửi, công việc được tạo, webhook được gọi như khi luồng tự chạy.
            Muốn chỉ xem đường đi, dùng <b>Chạy thử</b>.</span
          >
        </div>
        <div class="form-actions">
          <button type="button" class="button secondary" @click="runDialog = false">Hủy</button
          ><button
            type="button"
            class="button"
            :disabled="!pickId || busy"
            :title="!pickId ? `Chọn một ${familyLabel} ở danh sách trên` : ''"
            @click="runNow"
          >
            <PlayCircle :size="16" />{{ busy ? 'Đang chạy…' : 'Chạy ngay' }}
          </button>
        </div>
      </div>
    </ModalDialog>
  </div>
  <ProcessPanel
    v-if="panelOpen && ruleId"
    :rule-id="ruleId"
    :dirty="dirty"
    :save="save"
    @close="panelOpen = false"
    @changed="processChanged"
  />
  <ProcessFormDialog
    v-if="editingForm && processFormDetail"
    :name="processFormDetail.name"
    :description="processFormDetail.description"
    :fields="processFormDetail.fields"
    @close="editingForm = false"
    @created="formRevised"
  />
</template>
