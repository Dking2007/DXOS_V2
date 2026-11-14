<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, provide, ref, watch } from 'vue'
import type { Ref } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import type { Edge, Node } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { MiniMap } from '@vue-flow/minimap'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/controls/dist/style.css'
import '@vue-flow/minimap/dist/style.css'
import './flow.css'
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Circle,
  Eye,
  FileText,
  Hourglass,
  Info,
  Maximize2,
  Minimize2,
  ScanSearch,
  XCircle,
} from 'lucide-vue-next'
import { api } from '../api'
import { formatDate, formatSize } from '@dx/web-shared/api.ts'
import { isOfficeFile, previewKind } from '../ui/preview'
import StatePanel from '@dx/web-shared/components/StatePanel.vue'
import FlowNode from './FlowNode.vue'
import { FLOW_CONTEXT } from './context'
import { KINDS, OUTCOMES, branchLabel, paintRun, toCanvas } from './nodes'
import type { ApiGraph, Branch, FlowNodeData, NodeKind, RunStep } from './nodes'

interface TaskItem {
  id: string
  node_id: string
  kind: 'approval' | 'opinion' | 'input'
  label: string
  state: string
  decision: string | null
  reason: string | null
  assignee_name: string
  decided_by_name: string
  decided_at: string | null
  due_at: string | null
  values?: Record<string, unknown> | null
}
type Step = RunStep & {
  answered?: number
  total?: number
  decided_by?: string
  reason?: string
  opinions?: { by: string; decision: string; reason: string }[]
  superseded?: boolean
  attempt?: number
  at?: string
  done_at?: string
}
interface ProcessView {
  mode: 'process' | 'steps' | 'preview'
  graph: ApiGraph
  steps: Step[]
  tasks: TaskItem[]
  people: Record<string, string>
  departments: Record<string, string>
  submissions: { id: string; number: number; state: string; created_at: string }[]
  submission_id: string | null
  outcome: string | null
  state: string | null
  rule_name: string | null
  /** Per step: the documents it asks for and the files handed in there. */
  files?: Record<string, StepFiles>
}
export interface StepFile {
  id: string
  name: string
  mime: string | null
  size: number | null
  by: string
  at: string | null
  source: 'dossier' | 'step' | 'task'
  available: boolean
}
interface StepFiles {
  required: number
  documents: string[]
  attached: StepFile[]
  hidden: boolean
}
/** One stop on the dossier's journey, in the order it happened. */
interface Stop {
  key: string
  order: number
  nodeId: string
  kind: NodeKind
  title: string
  step: Step
}
const props = defineProps<{ caseId: string; status: string; formId: string; formName: string }>()
const emit = defineEmits<{ open: [file: StepFile, submissionId: string | null] }>()
const submissionId = ref('')
const view = useQuery({
  queryKey: computed(() => ['case-process', props.caseId, submissionId.value, props.status]),
  queryFn: () =>
    api.request<ProcessView>(
      `/cases/${props.caseId}/process${submissionId.value ? `?submission_id=${submissionId.value}` : ''}`,
    ),
  refetchInterval: computed(() => (['pending_workflow_start', 'processing'].includes(props.status) ? 8000 : false)),
})
const nodes = ref([]) as Ref<Node<FlowNodeData>[]>
const edges = ref([]) as Ref<Edge[]>
const selectedId = ref<string | null>(null)
const expanded = ref(false)
const { fitView, onNodeClick, onNodesInitialized, onPaneClick } = useVueFlow({ id: `case-process-${props.caseId}` })
function fitAll(duration = 0) {
  void fitView({ padding: 0.12, maxZoom: 1.05, duration })
}
// Sizes are known only once the nodes are measured; fitting earlier leaves wide flows cut off.
onNodesInitialized(() => fitAll())
onNodeClick(({ node }) => (selectedId.value = node.id))
onPaneClick(() => (selectedId.value = null))

const graphNodes = computed(() => new Map((view.data.value?.graph.nodes ?? []).map((node) => [node.id, node])))
function titleOf(nodeId: string) {
  const node = graphNodes.value.get(nodeId)
  if (!node) return nodeId
  if (node.type === 'trigger') return 'Trình hồ sơ'
  return node.label || KINDS[node.type]?.title || node.type
}
/** The steps in the order the dossier went through them, earlier passes of a step included. */
const journey = computed<Stop[]>(() => {
  const data = view.data.value
  if (!data || data.mode === 'preview') return []
  return data.steps
    .filter((step) => step.node_id && graphNodes.value.has(step.node_id))
    .map((step, index) => ({
      key: `${step.node_id}-${index}`,
      order: index + 1,
      nodeId: step.node_id!,
      kind: graphNodes.value.get(step.node_id!)!.type,
      title: titleOf(step.node_id!),
      step,
    }))
})
const settled = computed(() => view.data.value?.steps.find((step) => step.type === 'outcome'))

watch(
  () => [view.data.value, journey.value] as const,
  ([data]) => {
    if (!data) return
    const canvas = toCanvas(data.graph)
    for (const node of canvas.nodes) {
      node.draggable = false
      node.connectable = false
      node.deletable = false
    }
    if (data.mode === 'preview') {
      nodes.value = canvas.nodes
      edges.value = canvas.edges
      return
    }
    const painted = paintRun(canvas.nodes, canvas.edges, data.steps)
    const orders = new Map<string, number[]>()
    for (const stop of journey.value) orders.set(stop.nodeId, [...(orders.get(stop.nodeId) ?? []), stop.order])
    nodes.value = painted.nodes.map((node) => ({ ...node, data: { ...node.data!, order: orders.get(node.id) } }))
    const status = new Map(nodes.value.map((node) => [node.id, node.data?.status]))
    // The path taken is solid, the leg into a step still waiting moves, everything else fades.
    edges.value = painted.edges.map((edge) => {
      const taken = !!edge.animated
      const current = taken && status.get(edge.target) === 'waiting'
      return {
        ...edge,
        animated: current,
        class: [edge.class, taken ? '' : 'edge-idle', current ? 'edge-current' : ''].filter(Boolean).join(' '),
        zIndex: taken ? 2 : 0,
      }
    })
  },
  { immediate: true },
)
provide(FLOW_CONTEXT, {
  triggers: ref([]),
  userName: (id: string) => view.data.value?.people[id] || 'người được chọn',
  overlay: computed(() => view.data.value?.mode !== 'preview'),
  addAfter: () => undefined,
  forms: computed(() => [{ id: props.formId, name: props.formName }]),
  readonly: true,
})

function tasksOf(nodeId: string) {
  return (view.data.value?.tasks ?? []).filter((task) => task.node_id === nodeId)
}
const waiting = computed(() =>
  journey.value
    .filter((stop) => stop.step.state === 'waiting' && !stop.step.superseded)
    .map((stop) => ({
      ...stop,
      people: tasksOf(stop.nodeId)
        .filter((task) => task.state === 'pending' || task.state === 'syncing')
        .map((task) => task.assignee_name),
      due: tasksOf(stop.nodeId).find((task) => task.due_at && task.state === 'pending')?.due_at ?? null,
    })),
)
const done = computed(() => journey.value.filter((stop) => stop.step.state === 'succeeded' && stop.kind !== 'trigger').length)
const remaining = computed(() => {
  const visited = new Set(journey.value.map((stop) => stop.nodeId))
  return (view.data.value?.graph.nodes ?? []).filter((node) => !visited.has(node.id) && node.type !== 'trigger').length
})
const failed = computed(
  () =>
    !settled.value &&
    (view.data.value?.state === 'failed' ||
      view.data.value?.state === 'configuration_error' ||
      journey.value.some((stop) => stop.step.state === 'failed' && !stop.step.superseded)),
)
/** The latest pass of the chosen step, and every pass of it. */
const selectedStops = computed(() => journey.value.filter((stop) => stop.nodeId === selectedId.value))
const selectedStep = computed(() => selectedStops.value.at(-1)?.step)
const selectedNode = computed(() => (selectedId.value ? graphNodes.value.get(selectedId.value) : undefined))
const selectedFiles = computed(() => (selectedId.value ? view.data.value?.files?.[selectedId.value] : undefined))
// Steps where documents come in: handing in the dossier, and the steps people answer or work on.
const FILE_KINDS = new Set(['trigger', 'approval', 'consult', 'input', 'acknowledge', 'assign_task'])
const showFiles = computed(() => {
  const files = selectedFiles.value
  if (!files) return false
  const kind = selectedNode.value?.type ?? ''
  return FILE_KINDS.has(kind) || files.required > 0 || files.documents.length > 0 || files.attached.length > 0
})
const asksNothing = computed(() => {
  const files = selectedFiles.value
  return !!files && !files.required && !files.documents.length
})
const FILE_SOURCE: Record<StepFile['source'], string> = {
  dossier: 'Kèm khi trình',
  step: 'Nộp ở bước này',
  task: 'Kết quả công việc',
}
/** Whether a file can be read in the browser: office documents in the editor, others in the viewer. */
function viewable(file: StepFile) {
  return file.available && (isOfficeFile(file.name) || !!previewKind(file.name, file.mime))
}
const infoOpen = ref<string | null>(null)
function openFile(file: StepFile) {
  // Files handed in with the submission open at the version that was submitted.
  emit('open', file, file.source === 'dossier' ? (view.data.value?.submission_id ?? null) : null)
}
/** Plain values a step's people filled in; the files they handed in are listed on their own. */
function shownValues(values: Record<string, unknown> | null | undefined) {
  return Object.entries(values ?? {})
    .filter(([key]) => !key.startsWith('_'))
    .map(([, value]) => String(value))
}

function focus(nodeId: string) {
  selectedId.value = nodeId
  void fitView({ nodes: [nodeId], padding: 1.6, maxZoom: 1.1, duration: 400 })
}
function backToJourney() {
  selectedId.value = null
  fitAll(300)
}
function toggleExpanded() {
  expanded.value = !expanded.value
  void nextTick(() => setTimeout(() => fitAll(250), 60))
}
function onKey(event: KeyboardEvent) {
  if (event.key === 'Escape' && expanded.value) toggleExpanded()
}
onMounted(() => window.addEventListener('keydown', onKey))
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))

const STATE: Record<string, string> = {
  succeeded: 'Đã xong',
  waiting: 'Đang chờ',
  failed: 'Không thực hiện được',
  cancelled: 'Đã dừng',
  skipped: 'Bỏ qua',
  queued: 'Đang gửi',
  unknown: 'Chưa rõ kết quả',
}
const TASK_STATE: Record<string, string> = {
  pending: 'Đang chờ',
  syncing: 'Đang ghi nhận',
  completed: 'Đã trả lời',
  cancelled: 'Đã đóng',
}
const DECISION: Record<string, string> = { approve: 'Duyệt', return: 'Trả lại', reject: 'Từ chối' }
function decisionText(task: TaskItem) {
  if (!task.decision) return ''
  if (task.kind === 'opinion') return task.decision === 'approve' ? 'Đồng ý' : 'Không đồng ý'
  if (task.kind === 'input') return 'Đã nộp'
  return DECISION[task.decision] ?? task.decision
}
function stopLine(stop: Stop) {
  const parts: string[] = []
  if (stop.step.branch) parts.push(`→ ${branchLabel(stop.kind, stop.step.branch as Branch)}`)
  if (stop.step.decided_by) parts.push(stop.step.decided_by)
  else if (stop.step.people?.length) parts.push(stop.step.people.join(', '))
  if (stop.step.total) parts.push(`${stop.step.answered ?? 0}/${stop.step.total} ý kiến`)
  return parts.join(' · ')
}
const modeText = computed(() => {
  const data = view.data.value
  if (!data) return ''
  if (data.mode === 'preview')
    return data.rule_name
      ? `Khi trình, hồ sơ sẽ đi theo quy trình “${data.rule_name}”.`
      : 'Khi trình, hồ sơ đi theo các bước duyệt của biểu mẫu.'
  if (data.mode === 'process') return `Quy trình “${data.rule_name ?? ''}”, đúng phiên bản lúc trình hồ sơ.`
  return 'Các bước duyệt của biểu mẫu, vẽ dạng sơ đồ.'
})
</script>
<template>
  <section class="card pc" :class="{ expanded }" aria-label="Quy trình xử lý hồ sơ">
    <header class="pc-head">
      <div class="pc-title">
        <span class="eyebrow">QUY TRÌNH</span>
        <h2>Hồ sơ đang ở đâu</h2>
        <small class="muted">{{ modeText }}</small>
      </div>
      <div class="pc-tools">
        <label v-if="(view.data.value?.submissions.length ?? 0) > 1" class="scope-select"
          >Lần trình
          <select v-model="submissionId" aria-label="Chọn lần trình">
            <option value="">Mới nhất</option>
            <option v-for="item in view.data.value?.submissions" :key="item.id" :value="item.id">
              Lần {{ item.number }} · {{ formatDate(item.created_at, true) }}
            </option>
          </select></label
        >
        <button class="button secondary small" type="button" title="Xem toàn bộ quy trình" @click="fitAll(300)">
          <ScanSearch :size="15" />Vừa khung
        </button>
        <button class="button secondary small" type="button" @click="toggleExpanded">
          <component :is="expanded ? Minimize2 : Maximize2" :size="15" />{{ expanded ? 'Thu nhỏ' : 'Toàn màn hình' }}
        </button>
      </div>
    </header>
    <StatePanel
      v-if="view.isPending.value || view.error.value"
      :loading="view.isPending.value"
      :error="view.error.value"
      compact
      @retry="view.refetch()"
    />
    <template v-else-if="view.data.value">
      <div
        class="pc-status"
        :class="
          settled
            ? `is-${settled.outcome}`
            : failed
              ? 'is-failed'
              : view.data.value.mode === 'preview'
                ? 'is-preview'
                : 'is-waiting'
        "
      >
        <span class="pc-status-icon">
          <CheckCircle2 v-if="settled?.outcome === 'approved'" :size="22" />
          <XCircle v-else-if="settled?.outcome === 'rejected'" :size="22" />
          <AlertTriangle v-else-if="settled || failed" :size="22" />
          <Eye v-else-if="view.data.value.mode === 'preview'" :size="22" />
          <Hourglass v-else :size="22" />
        </span>
        <div class="pc-status-text">
          <template v-if="settled">
            <strong>{{ OUTCOMES[settled.outcome ?? ''] ?? settled.outcome }}</strong>
            <small
              >Kết thúc tại bước “{{ titleOf(settled.source ?? '') }}”<template v-if="settled.at">
                lúc {{ formatDate(settled.at, true) }}</template
              ><template v-if="settled.message">. {{ settled.message }}</template></small
            >
          </template>
          <template v-else-if="failed">
            <strong>Quy trình dừng lại, chưa có kết quả</strong>
            <small>Người quản trị quy trình đã được báo. Bước lỗi được đánh dấu đỏ trên sơ đồ.</small>
          </template>
          <template v-else-if="view.data.value.mode === 'preview'">
            <strong>Hồ sơ chưa trình</strong>
            <small>Đây là đường đi dự kiến; nhánh thực tế tùy nội dung hồ sơ và quyết định ở từng bước.</small>
          </template>
          <template v-else-if="waiting.length">
            <strong
              >Đang chờ:
              <template v-for="(item, index) in waiting" :key="item.key"
                >{{ index ? ', ' : '' }}{{ item.title }}</template
              ></strong
            >
            <small>
              <template v-for="(item, index) in waiting" :key="item.key"
                >{{ index ? ' · ' : ''
                }}<template v-if="item.people.length">{{ item.people.join(', ') }}</template
                ><template v-else>{{ STATE.waiting }}</template
                ><template v-if="item.step.attempt"> (lần {{ item.step.attempt }})</template
                ><template v-if="item.due"> · hạn {{ formatDate(item.due) }}</template></template
              >
            </small>
          </template>
          <template v-else>
            <strong>Đang xử lý</strong>
            <small>Hệ thống đang chuyển hồ sơ sang bước tiếp theo.</small>
          </template>
        </div>
        <div v-if="view.data.value.mode !== 'preview'" class="pc-progress" aria-label="Tiến độ">
          <span><b>{{ done }}</b> bước đã xong</span>
          <span v-if="waiting.length"><b>{{ waiting.length }}</b> đang chờ</span>
          <span v-if="!settled && remaining"><b>{{ remaining }}</b> chưa tới</span>
        </div>
      </div>

      <div class="pc-body">
        <div class="pc-canvas">
          <VueFlow
            v-model:nodes="nodes"
            v-model:edges="edges"
            :nodes-draggable="false"
            :nodes-connectable="false"
            :edges-updatable="false"
            :delete-key-code="null"
            :zoom-on-scroll="expanded"
            :zoom-on-pinch="true"
            :pan-on-scroll="!expanded"
            :min-zoom="0.25"
            :max-zoom="1.6"
          >
            <template #node-flow="nodeProps"><FlowNode v-bind="nodeProps" /></template>
            <Background :gap="22" :size="1.3" pattern-color="#cfd9e2" />
            <Controls position="bottom-left" :show-interactive="false" />
            <MiniMap
              position="bottom-right"
              pannable
              zoomable
              :node-color="(node: Node<FlowNodeData>) => (node.data?.status ? KINDS[node.data.kind].color : '#c9d4dd')"
              :node-stroke-width="0"
            />
          </VueFlow>
          <div class="pc-legend" aria-hidden="true">
            <span class="legend done">Đã xong</span><span class="legend wait">Đang chờ</span
            ><span class="legend stop">Dừng / bỏ qua</span><span class="legend fail">Lỗi</span
            ><span class="legend path">Đường đã đi</span>
          </div>
        </div>

        <aside class="pc-side">
          <template v-if="selectedNode">
            <button class="button ghost small pc-back" type="button" @click="backToJourney">
              <ArrowLeft :size="15" />Đường đi của hồ sơ
            </button>
            <div class="pc-detail">
              <span class="pc-kind" :style="{ '--node-color': KINDS[selectedNode.type]?.color }"
                ><component :is="KINDS[selectedNode.type]?.icon" :size="15" />{{ KINDS[selectedNode.type]?.title }}</span
              >
              <h3>{{ titleOf(selectedNode.id) }}</h3>
              <p v-if="!selectedStep" class="muted">
                {{ view.data.value.mode === 'preview' ? 'Bước này có trong quy trình.' : 'Hồ sơ chưa đi qua bước này.' }}
              </p>
              <template v-else>
                <div class="pc-facts">
                  <span class="pc-state" :class="`st-${selectedStep.state}`">{{
                    STATE[selectedStep.state] ?? selectedStep.state
                  }}</span>
                  <span v-if="selectedStep.branch"
                    >Đi nhánh <b>“{{ branchLabel(selectedNode.type, selectedStep.branch as Branch) }}”</b></span
                  >
                  <span v-if="selectedStops.length > 1">Đã đi qua {{ selectedStops.length }} lần</span>
                </div>
                <dl class="pc-times">
                  <template v-if="selectedStep.at"
                    ><dt>Tới bước</dt>
                    <dd>{{ formatDate(selectedStep.at, true) }}</dd></template
                  >
                  <template v-if="selectedStep.done_at"
                    ><dt>Xong lúc</dt>
                    <dd>{{ formatDate(selectedStep.done_at, true) }}</dd></template
                  >
                </dl>
                <p v-if="selectedStep.message" class="pc-message">{{ selectedStep.message }}</p>
                <p v-if="selectedStep.total">
                  Đã có <b>{{ selectedStep.answered ?? 0 }}/{{ selectedStep.total }}</b> người trả lời.
                </p>
              </template>
              <div v-if="tasksOf(selectedNode.id).length" class="pc-people">
                <span class="section-label">Người xử lý</span>
                <div v-for="task in tasksOf(selectedNode.id)" :key="task.id" class="pc-person">
                  <span class="avatar">{{ task.assignee_name.split(' ').slice(-1)[0]?.slice(0, 1) }}</span>
                  <div class="grow">
                    <p>
                      <b>{{ task.assignee_name }}</b>
                      <template v-if="task.decided_by_name && task.decided_by_name !== task.assignee_name">
                        (do {{ task.decided_by_name }} xử lý thay)</template
                      >
                    </p>
                    <small v-if="task.reason" class="pc-quote">“{{ task.reason }}”</small>
                    <small v-if="shownValues(task.values).length">{{ shownValues(task.values).join(' · ') }}</small>
                    <small v-if="task.decided_at" class="muted">{{ formatDate(task.decided_at, true) }}</small>
                    <small v-else-if="task.due_at && task.state === 'pending'" class="muted"
                      >Hạn {{ formatDate(task.due_at) }}</small
                    >
                  </div>
                  <span class="tag" :class="task.decision ? `dec-${task.decision}` : ''">{{
                    decisionText(task) || TASK_STATE[task.state] || task.state
                  }}</span>
                </div>
              </div>
              <div v-if="showFiles && selectedFiles" class="pc-files">
                <span class="section-label">Tài liệu</span>
                <p v-if="selectedFiles.hidden" class="muted">Bước của bạn không được xem tài liệu của hồ sơ.</p>
                <template v-else>
                  <p v-if="selectedFiles.required" class="pc-files-need" :class="{ met: selectedFiles.attached.length >= selectedFiles.required }">
                    Cần ít nhất <b>{{ selectedFiles.required }}</b> tệp · đã có
                    <b>{{ selectedFiles.attached.length }}</b>
                  </p>
                  <ul v-if="selectedFiles.documents.length" class="pc-docs">
                    <li v-for="name in selectedFiles.documents" :key="name">
                      <Circle :size="12" aria-hidden="true" />{{ name }}
                    </li>
                  </ul>
                  <ul v-if="selectedFiles.attached.length" class="pc-file-list">
                    <li v-for="file in selectedFiles.attached" :key="`${file.source}-${file.id}`">
                      <div class="pc-file">
                        <button
                          type="button"
                          class="pc-file-open"
                          :disabled="!viewable(file)"
                          :title="viewable(file) ? (isOfficeFile(file.name) ? 'Mở bằng trình soạn thảo (chỉ xem)' : 'Xem tệp') : 'Không xem trước được tệp này'"
                          @click="openFile(file)"
                        >
                          <FileText :size="16" aria-hidden="true" />
                          <span class="grow">
                            <strong>{{ file.name }}</strong>
                            <small>{{ FILE_SOURCE[file.source] }}<template v-if="!file.available"> · đã xóa khỏi kho</template></small>
                          </span>
                        </button>
                        <button
                          type="button"
                          class="icon-button"
                          :aria-expanded="infoOpen === file.id"
                          :aria-label="`Thông tin ${file.name}`"
                          title="Thông tin tệp"
                          @click="infoOpen = infoOpen === file.id ? null : file.id"
                        >
                          <Info :size="15" />
                        </button>
                      </div>
                      <dl v-if="infoOpen === file.id" class="pc-file-info">
                        <template v-if="file.by"><dt>Người nộp</dt><dd>{{ file.by }}</dd></template>
                        <template v-if="file.at"><dt>Thời điểm</dt><dd>{{ formatDate(file.at, true) }}</dd></template>
                        <template v-if="file.size != null"><dt>Dung lượng</dt><dd>{{ formatSize(file.size) }}</dd></template>
                        <dt>Nguồn</dt><dd>{{ FILE_SOURCE[file.source] }}</dd>
                      </dl>
                    </li>
                  </ul>
                  <p v-else class="muted">
                    {{ asksNothing ? 'Bước này không yêu cầu tài liệu.' : 'Chưa có tệp nào ở bước này.' }}
                  </p>
                </template>
              </div>
            </div>
          </template>
          <template v-else>
            <span class="section-label">{{ view.data.value.mode === 'preview' ? 'Các bước' : 'Đường đi của hồ sơ' }}</span>
            <ol v-if="journey.length" class="pc-journey">
              <li
                v-for="stop in journey"
                :key="stop.key"
                :class="[`st-${stop.step.state}`, { old: stop.step.superseded }]"
              >
                <button type="button" @click="focus(stop.nodeId)">
                  <span class="pc-dot">{{ stop.order }}</span>
                  <span class="grow">
                    <strong>{{ stop.title }}</strong>
                    <small>
                      {{ STATE[stop.step.state] ?? stop.step.state
                      }}<template v-if="stopLine(stop)"> · {{ stopLine(stop) }}</template
                      ><template v-if="stop.step.superseded"> · lượt cũ</template>
                    </small>
                    <small v-if="stop.step.done_at || stop.step.at" class="muted">{{
                      formatDate(stop.step.done_at ?? stop.step.at ?? '', true)
                    }}</small>
                  </span>
                </button>
              </li>
              <li v-if="settled" :class="`end is-${settled.outcome}`">
                <span class="pc-dot">✓</span>
                <span class="grow">
                  <strong>{{ OUTCOMES[settled.outcome ?? ''] ?? settled.outcome }}</strong>
                  <small v-if="settled.at" class="muted">{{ formatDate(settled.at, true) }}</small>
                </span>
              </li>
            </ol>
            <ol v-else class="pc-journey">
              <li v-for="node in view.data.value.graph.nodes.filter((n) => n.type !== 'trigger')" :key="node.id">
                <button type="button" @click="focus(node.id)">
                  <span class="pc-dot" :style="{ background: KINDS[node.type]?.color }"
                    ><component :is="KINDS[node.type]?.icon" :size="13"
                  /></span>
                  <span class="grow"
                    ><strong>{{ titleOf(node.id) }}</strong><small>{{ KINDS[node.type]?.title }}</small></span
                  >
                </button>
              </li>
            </ol>
            <p class="muted pc-hint">Bấm một bước trong danh sách hoặc trên sơ đồ để xem ai xử lý, quyết định gì.</p>
          </template>
        </aside>
      </div>
    </template>
  </section>
</template>
<style scoped>
.pc {
  overflow: hidden;
  padding: 0;
}
.pc.expanded {
  position: fixed;
  inset: 12px;
  z-index: 200;
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-lg);
}
.pc-head {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 18px;
  align-items: flex-end;
  justify-content: space-between;
  padding: 18px 22px 14px;
}
.pc-title h2 {
  margin: 2px 0 2px;
  font-size: 20px;
}
.pc-tools {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.pc-status {
  --tone: #b07812;
  --tone-bg: color-mix(in srgb, #d39a2c 13%, var(--surface));
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  align-items: center;
  margin: 0 22px 16px;
  padding: 14px 18px;
  border: 1px solid color-mix(in srgb, var(--tone) 30%, transparent);
  border-radius: 14px;
  background: var(--tone-bg);
}
.pc-status.is-approved {
  --tone: var(--green-ink);
  --tone-bg: var(--green-soft);
}
.pc-status.is-rejected,
.pc-status.is-failed {
  --tone: var(--red);
  --tone-bg: var(--red-soft);
}
.pc-status.is-preview {
  --tone: var(--muted);
  --tone-bg: var(--surface-2);
}
.pc-status-icon {
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  border-radius: 12px;
  color: #fff;
  background: var(--tone);
  flex: none;
}
.pc-status-text {
  display: grid;
  gap: 2px;
  flex: 1;
  min-width: 220px;
}
.pc-status-text strong {
  font-size: 16px;
  color: var(--tone);
}
.pc-progress {
  display: flex;
  gap: 16px;
  font-size: 13px;
  color: var(--muted);
}
.pc-progress b {
  display: block;
  font-size: 20px;
  line-height: 1.1;
  color: var(--text, inherit);
}
.pc-body {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  border-top: 1px solid var(--border);
  min-height: 0;
}
.pc.expanded .pc-body {
  flex: 1;
}
.pc-canvas {
  position: relative;
  height: clamp(540px, 72vh, 900px);
  background: var(--surface-2);
}
.pc.expanded .pc-canvas {
  height: auto;
  min-height: 0;
}
.pc-legend {
  position: absolute;
  top: 12px;
  left: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  padding: 7px 12px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: color-mix(in srgb, var(--surface) 92%, transparent);
  backdrop-filter: blur(6px);
  font-size: 12.5px;
  pointer-events: none;
}
.legend::before {
  content: '';
  display: inline-block;
  width: 10px;
  height: 10px;
  margin-right: 6px;
  border-radius: 3px;
  border: 2px solid;
  vertical-align: -1px;
}
.legend.done::before {
  border-color: #3fae7d;
}
.legend.wait::before {
  border-color: #d39a2c;
}
.legend.stop::before {
  border-color: #8fa3b5;
  border-style: dashed;
}
.legend.fail::before {
  border-color: var(--red);
}
.legend.path::before {
  width: 18px;
  height: 0;
  border-radius: 0;
  border-width: 2px 0 0;
  border-color: var(--green-ink);
  vertical-align: 3px;
}
.pc-side {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 16px 18px;
  border-left: 1px solid var(--border);
  overflow-y: auto;
  max-height: clamp(540px, 72vh, 900px);
}
.pc.expanded .pc-side {
  max-height: none;
}
.pc-journey {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  position: relative;
}
.pc-journey li {
  position: relative;
}
/* The thread joining the stops, so the list reads as one path. */
.pc-journey li:not(:last-child)::before {
  content: '';
  position: absolute;
  left: 21px;
  top: 34px;
  bottom: -6px;
  width: 2px;
  background: var(--border);
}
.pc-journey li.st-succeeded:not(:last-child)::before {
  background: #3fae7d;
}
.pc-journey button,
.pc-journey li.end {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  width: 100%;
  padding: 8px 8px;
  border: 0;
  border-radius: 10px;
  background: none;
  color: inherit;
  text-align: left;
  cursor: pointer;
}
.pc-journey li.end {
  cursor: default;
}
.pc-journey button:hover,
.pc-journey button:focus-visible {
  background: var(--surface-2);
}
.pc-journey .grow {
  display: grid;
  gap: 1px;
  min-width: 0;
}
.pc-journey small {
  font-size: 12.5px;
  color: var(--muted);
}
.pc-dot {
  position: relative;
  z-index: 1;
  display: grid;
  place-items: center;
  flex: none;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  font-size: 12.5px;
  font-weight: 700;
  color: #fff;
  background: #8fa3b5;
}
.st-succeeded .pc-dot {
  background: #3fae7d;
}
.st-waiting .pc-dot {
  background: #d39a2c;
  box-shadow: 0 0 0 4px color-mix(in srgb, #d39a2c 25%, transparent);
}
.st-failed .pc-dot {
  background: var(--red);
}
.pc-journey li.old {
  opacity: 0.6;
}
.end.is-approved .pc-dot {
  background: var(--green-ink);
}
.end.is-rejected .pc-dot {
  background: var(--red);
}
.end.is-needs_revision .pc-dot {
  background: #d39a2c;
}
.pc-hint {
  margin-top: auto;
  font-size: 12.5px;
}
.pc-back {
  align-self: flex-start;
}
.pc-detail {
  display: grid;
  gap: 10px;
}
.pc-detail h3 {
  margin: 0;
  font-size: 18px;
}
.pc-kind {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  font-size: 12.5px;
  font-weight: 700;
  color: var(--node-color);
}
.pc-facts {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 12px;
  align-items: center;
  font-size: 13.5px;
}
.pc-state {
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 12.5px;
  font-weight: 700;
  background: var(--surface-2);
}
.pc-state.st-succeeded {
  color: var(--green-ink);
  background: var(--green-soft);
}
.pc-state.st-waiting {
  color: #a8700f;
  background: color-mix(in srgb, #d39a2c 16%, transparent);
}
.pc-state.st-failed {
  color: var(--red);
  background: var(--red-soft);
}
.pc-times {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 4px 12px;
  margin: 0;
  font-size: 13.5px;
}
.pc-times dt {
  color: var(--muted);
}
.pc-times dd {
  margin: 0;
}
.pc-message {
  padding: 10px 12px;
  border-left: 3px solid var(--border);
  background: var(--surface-2);
  border-radius: 0 8px 8px 0;
}
.pc-people {
  display: grid;
  gap: 8px;
}
.pc-person {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  padding: 10px;
  border: 1px solid var(--border);
  border-radius: 10px;
}
.pc-person .grow {
  display: grid;
  gap: 2px;
  min-width: 0;
}
.pc-person p {
  margin: 0;
}
.pc-quote {
  font-style: italic;
}
.tag.dec-approve {
  color: var(--green-ink);
  background: var(--green-soft);
}
.tag.dec-reject {
  color: var(--red);
  background: var(--red-soft);
}
.tag.dec-return {
  color: #a8700f;
  background: color-mix(in srgb, #d39a2c 16%, transparent);
}
@media (max-width: 1100px) {
  .pc-body {
    grid-template-columns: 1fr;
  }
  .pc-side {
    border-left: 0;
    border-top: 1px solid var(--border);
    max-height: none;
  }
  .pc-canvas {
    height: clamp(420px, 60vh, 640px);
  }
}
</style>
