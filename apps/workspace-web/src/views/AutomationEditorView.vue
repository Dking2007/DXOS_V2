<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, provide, ref, watch } from 'vue'
import type { Ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { useUnsavedGuard } from '../ui/unsaved'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import type { Connection, Edge, Node } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { MiniMap } from '@vue-flow/minimap'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/controls/dist/style.css'
import '@vue-flow/minimap/dist/style.css'
import '../flow/flow.css'
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  FlaskConical,
  History,
  Info,
  PanelBottomClose,
  Play,
  PlayCircle,
  Power,
  Save,
  Search,
  X,
  Zap,
  FilePen,
  Rocket,
} from 'lucide-vue-next'
import ModalDialog from '@dx/web-shared/components/ModalDialog.vue'
import { api } from '../api'
import { ApiError, errorText, formatDate } from '@dx/web-shared/api.ts'
import type { Page } from '@dx/web-shared/api.ts'
import type { Department, FormTemplate, User } from '@dx/web-shared/types.ts'
import StatusBadge from '@dx/web-shared/components/StatusBadge.vue'
import FlowNode from '../flow/FlowNode.vue'
import NodeInspector from '../flow/NodeInspector.vue'
import ProcessFormDialog from '../flow/ProcessFormDialog.vue'
import ProcessPanel from '../flow/ProcessPanel.vue'
import { FLOW_CONTEXT } from '../flow/context'
import {
  KINDS,
  OUTCOMES,
  PROCESS_TEMPLATES,
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
const catalog = useQuery({
  queryKey: ['automations', 'catalog'],
  queryFn: () => api.request<Catalog>('/automations/catalog'),
})
const users = useQuery({ queryKey: ['users'], queryFn: () => api.request<Page<User>>('/users') })
const departments = useQuery({
  queryKey: ['departments'],
  queryFn: () => api.request<Page<Department>>('/departments'),
})
const connections = useQuery({
  queryKey: ['connections'],
  queryFn: () => api.request<Page<{ id: string; name: string; base_url: string }>>('/connections'),
})
const triggers = computed(() => catalog.data.value?.triggers ?? [])
function userName(id: string) {
  return users.data.value?.items.find((u) => u.id === id)?.display_name ?? id.slice(0, 8)
}

// A form on the trigger makes the flow the route of that form's dossiers; nothing else differs.
const isProcess = computed(() => !!triggerNode.value?.data?.config.form_id)
const forms = computed(() => catalog.data.value?.process.forms ?? [])
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
const { fitView, screenToFlowCoordinate, onConnect, onNodeClick, onPaneClick, onEdgeClick, onNodesInitialized } =
  useVueFlow({ id: 'automation-flow' })

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
    fitView({ padding: 0.2, maxZoom: 1 })
  })
})
function snapshot() {
  return JSON.stringify({
    g: toApi(nodes.value, edges.value),
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
  const list = [...TEMPLATES, ...PROCESS_TEMPLATES]
  const template = list.find((t) => t.key === route.query.template) ?? list[0]
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
function addNode(kind: NodeKind, position: { x: number; y: number }, after?: { id: string; handle?: string }) {
  if (kind === 'trigger' && triggerNode.value) {
    notice.value = 'Mỗi luồng chỉ có một node kích hoạt.'
    return
  }
  if (nodes.value.length >= (catalog.data.value?.max_nodes ?? 40)) {
    notice.value = 'Luồng đã đạt số node tối đa.'
    return
  }
  const id = newId(kind)
  nodes.value = [
    ...nodes.value,
    {
      id,
      type: 'flow',
      position,
      data: { kind, label: '', config: KINDS[kind].defaults() },
      deletable: kind !== 'trigger',
    },
  ]
  if (after) edges.value = [...edges.value, canvasEdge(after.id, id, after.handle)]
  selectedId.value = id
  clearOverlay()
}
const quickAdd = ref<{ id: string; handle?: string } | null>(null)
function addAfter(nodeId: string, handle?: string) {
  quickAdd.value = { id: nodeId, handle }
}
function pickQuick(kind: NodeKind) {
  const from = nodes.value.find((node) => node.id === quickAdd.value?.id)
  if (!from || !quickAdd.value) return
  const siblings = edges.value.filter((edge) => edge.source === from.id).length
  addNode(kind, { x: from.position.x + 320, y: from.position.y + siblings * 130 }, quickAdd.value)
  quickAdd.value = null
}
function onDragStart(event: DragEvent, kind: NodeKind) {
  event.dataTransfer?.setData('application/dx-node', kind)
  if (event.dataTransfer) event.dataTransfer.effectAllowed = 'move'
}
function onDrop(event: DragEvent) {
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
    addAfter(base.id, freeHandle(base))
    pickQuick(kind)
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
onNodeClick(({ node }) => (selectedId.value = node.id))
onPaneClick(() => {
  selectedId.value = null
  quickAdd.value = null
})
onEdgeClick(() => (selectedId.value = null))
function patch(values: Record<string, unknown>) {
  if (!selected.value?.data) return
  selected.value.data = { ...selected.value.data, config: { ...selected.value.data.config, ...values } }
  clearOverlay()
}
function setLabel(value: string) {
  if (selected.value?.data) selected.value.data = { ...selected.value.data, label: value }
}
function removeSelected() {
  const id = selectedId.value
  if (!id) return
  nodes.value = nodes.value.filter((node) => node.id !== id)
  edges.value = edges.value.filter((edge) => edge.source !== id && edge.target !== id)
  selectedId.value = null
}
function duplicateSelected() {
  const node = selected.value
  if (!node?.data) return
  addNode(node.data.kind, { x: node.position.x + 40, y: node.position.y + 120 })
  const copy = nodes.value.at(-1)!
  copy.data = { ...copy.data!, label: node.data.label, config: plainCopy(node.data.config) }
}

// ---- Live validation ----
const errors = ref<{ node_id: string | null; message: string }[]>([])
let validateTimer: ReturnType<typeof setTimeout> | undefined
watch(
  () => JSON.stringify(toApi(nodes.value, edges.value)),
  () => {
    clearTimeout(validateTimer)
    validateTimer = setTimeout(validate, 500)
  },
)
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
  fitView({ nodes: [id], padding: 1.2, maxZoom: 1.1, duration: 300 })
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
const pickId = ref('')
const candidates = useQuery({
  queryKey: computed(() => ['automation-candidates', ruleId.value, pickQuery.value]),
  queryFn: () =>
    api.request<{ items: { id: string; title: string; status: string | null }[] }>(
      `/automations/${ruleId.value}/candidates?q=${encodeURIComponent(pickQuery.value)}`,
    ),
  enabled: computed(() => runDialog.value && !!ruleId.value),
})
function openRunDialog() {
  pickId.value = ''
  pickQuery.value = ''
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
async function save() {
  if (busy.value) return
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
  } catch (cause) {
    error.value = cause
  } finally {
    busy.value = false
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
function onKey(event: KeyboardEvent) {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
    event.preventDefault()
    void save()
  }
}
onMounted(() => window.addEventListener('keydown', onKey))
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKey)
  clearTimeout(validateTimer)
})
watch(notice, (value) => value && setTimeout(() => (notice.value = ''), 2500))
useUnsavedGuard(dirty)

provide(FLOW_CONTEXT, { triggers, userName, overlay, addAfter, forms })
const ai = useAi()
const offeredKinds = computed(() =>
  paletteKinds().filter((kind) => !['ai', 'ai_extract'].includes(kind) || ai.on('automation_ai')),
)
const palette = computed(() =>
  (['Bước cần người', 'Logic', 'Hành động', 'Dữ liệu và tài liệu'] as const).map(
    (group) => ({ group, kinds: offeredKinds.value.filter((kind) => KINDS[kind].group === group) }),
  ),
)
</script>
<template>
  <div class="flow-editor">
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
      <span
        v-if="errors.length"
        class="flow-issues"
        role="button"
        tabindex="0"
        :title="errors.map((e) => e.message).join('\n')"
        @click="focusNode(errors[0].node_id)"
        @keydown.enter="focusNode(errors[0].node_id)"
        ><AlertTriangle :size="15" /> {{ errors.length }} vấn đề</span
      >
      <span v-else-if="nodes.length > 1" class="flow-ok"><CheckCircle2 :size="15" /> Hợp lệ</span>
      <button
        class="icon-button"
        :class="{ active: infoOpen }"
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
          :disabled="!ruleId"
          :title="ruleId ? '' : 'Lưu trước khi phát hành'"
          @click="panelOpen = true"
        >
          <Rocket :size="15" />Phát hành
        </button>
        <button
          v-if="isProcess && processFormDetail"
          class="button secondary small"
          @click="editingForm = true"
        >
          <FilePen :size="15" />Sửa biểu mẫu
        </button>
        <button class="button secondary small" :class="{ active: drawer === 'test' }" @click="drawer = drawer === 'test' ? null : 'test'">
          <FlaskConical :size="15" />Chạy thử
        </button>
        <button
          class="button secondary small"
          :disabled="!ruleId"
          :class="{ active: drawer === 'runs' }"
          @click="drawer = drawer === 'runs' ? null : 'runs'"
        >
          <History :size="15" />Lịch sử chạy
        </button>
        <button class="button small" :disabled="busy || (!dirty && !!ruleId)" title="Ctrl+S" @click="save">
          <Save :size="15" />{{ busy ? 'Đang lưu…' : 'Lưu' }}
        </button>
      </div>
    </header>
    <div class="flow-status" :class="{ on: enabled && ruleId, off: !enabled || !ruleId }">
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
    </div>
    <div v-if="error" class="notice error flow-alert" role="alert">
      <span>{{ errorText(error) }}</span
      ><button v-if="error instanceof ApiError && error.status === 409" class="button secondary small" @click="router.go(0)">
        Tải bản mới</button
      ><button class="icon-button" aria-label="Đóng" @click="error = null"><X :size="15" /></button>
    </div>
    <div class="flow-body">
      <aside class="flow-palette" aria-label="Các loại bước">
        <p class="muted">Kéo thả vào canvas hoặc bấm để thêm sau bước đang chọn.</p>
        <div v-for="section in palette" :key="section.group" class="palette-group">
          <span class="section-label">{{ section.group }}</span>
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
        </div>
      </aside>
      <section class="flow-canvas" @drop.prevent="onDrop" @dragover.prevent>
        <VueFlow
          v-model:nodes="nodes"
          v-model:edges="edges"
          :is-valid-connection="isValidConnection"
          :default-edge-options="{ type: 'smoothstep' }"
          :delete-key-code="['Delete', 'Backspace']"
          :snap-to-grid="true"
          :snap-grid="[20, 20]"
          :min-zoom="0.3"
          :max-zoom="1.6"
          :connection-radius="30"
          fit-view-on-init
        >
          <template #node-flow="nodeProps"><FlowNode v-bind="nodeProps" /></template>
          <Background :gap="20" :size="1.4" pattern-color="#c5d3de" />
          <Controls :show-interactive="false" position="bottom-left" />
          <MiniMap
            position="bottom-right"
            pannable
            zoomable
            :node-color="(node: Node<FlowNodeData>) => KINDS[node.data!.kind].color"
            :node-stroke-width="0"
          />
        </VueFlow>
        <div v-if="overlay" class="flow-overlay-bar">
          <Play :size="14" />{{ overlayTitle }}
          <button class="button ghost small" @click="clearOverlay">Ẩn kết quả</button>
        </div>
        <div v-if="notice" class="flow-toast">{{ notice }}</div>
        <div v-if="generalErrors.length" class="flow-general-errors">
          <AlertTriangle :size="15" />
          <span>{{ generalErrors.map((e) => e.message).join(' · ') }}</span>
        </div>
        <div v-if="quickAdd" class="quick-add" role="menu" aria-label="Thêm bước tiếp theo">
          <strong>Thêm bước tiếp theo</strong>
          <button
            v-for="kind in offeredKinds"
            :key="kind"
            class="palette-item"
            :style="{ '--node-color': KINDS[kind].color }"
            @click="pickQuick(kind)"
          >
            <span class="flow-node-icon small"><component :is="KINDS[kind].icon" :size="16" /></span>
            <span class="grow"><strong>{{ KINDS[kind].title }}</strong><small>{{ KINDS[kind].hint }}</small></span>
          </button>
          <button class="button ghost small" @click="quickAdd = null">Hủy</button>
        </div>
        <section v-if="drawer" class="flow-drawer">
          <header>
            <strong v-if="drawer === 'test'"><FlaskConical :size="15" /> Chạy thử với dữ liệu mẫu</strong>
            <strong v-else><History :size="15" /> Lịch sử chạy</strong>
            <button class="icon-button" aria-label="Đóng" @click="drawer = null"><PanelBottomClose :size="16" /></button>
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
              <button class="button" :disabled="busy" @click="runTest"><Play :size="15" />Chạy thử luồng</button>
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
            <p v-if="!runs.data.value?.items.length" class="muted">Luồng chưa chạy lần nào.</p>
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
      <aside v-if="selected?.data || infoOpen" class="flow-inspector">
        <button
          class="icon-button inspector-close"
          aria-label="Đóng bảng cấu hình"
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
          :users="users.data.value?.items ?? []"
          :departments="departments.data.value?.items ?? []"
          :connections="connections.data.value?.items ?? []"
          :webhooks-enabled="!!catalog.data.value?.webhooks_enabled"
          :process="isProcess"
          :forms="forms"
          :subprocesses="catalog.data.value?.process.subprocesses?.filter((item) => item.id !== ruleId)"
          @patch="patch"
          @label="setLabel"
          @remove="removeSelected"
          @duplicate="duplicateSelected"
        />
        <div v-else class="inspector">
          <header class="inspector-head">
            <span class="flow-node-icon small" style="--node-color: #5b6b7d"><Info :size="16" /></span>
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
                <li>Kéo node từ cột trái vào canvas, hoặc bấm <b>+</b> ở mép phải một node.</li>
                <li>Kéo từ chấm tròn bên phải sang node khác để nối. Node <b>Điều kiện</b> có hai cổng Đúng/Sai.</li>
                <li>Chọn node để cấu hình; chọn đường nối và bấm <kbd>Delete</kbd> để xóa.</li>
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
          ><button type="button" class="button" :disabled="!pickId || busy" @click="runNow">
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
