<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { computed, nextTick, provide, ref, watch } from 'vue'
import type { Ref } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import type { Edge, Node } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/controls/dist/style.css'
import './flow.css'
import { Hourglass, MousePointerClick } from 'lucide-vue-next'
import { api } from '../api'
import { formatDate } from '@dx/web-shared/api.ts'
import StatePanel from '@dx/web-shared/components/StatePanel.vue'
import FlowNode from './FlowNode.vue'
import { FLOW_CONTEXT } from './context'
import { KINDS, OUTCOMES, branchLabel, paintRun, toCanvas } from './nodes'
import type { ApiGraph, Branch, FlowNodeData, RunStep } from './nodes'

interface TaskItem {
  id: string
  node_id: string
  kind: 'approval' | 'opinion'
  label: string
  state: string
  decision: string | null
  reason: string | null
  assignee_name: string
  decided_by_name: string
  decided_at: string | null
  due_at: string | null
}
type Step = RunStep & {
  answered?: number
  total?: number
  decided_by?: string
  reason?: string
  opinions?: { by: string; decision: string; reason: string }[]
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
}
const props = defineProps<{ caseId: string; status: string; formId: string; formName: string }>()
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
const { fitView, onNodeClick, onPaneClick } = useVueFlow({ id: `case-process-${props.caseId}` })
onNodeClick(({ node }) => (selectedId.value = node.id))
onPaneClick(() => (selectedId.value = null))
watch(
  () => view.data.value,
  (data) => {
    if (!data) return
    const canvas = toCanvas(data.graph)
    for (const node of canvas.nodes) {
      node.draggable = false
      node.connectable = false
      node.deletable = false
    }
    const painted = data.mode === 'preview' ? canvas : paintRun(canvas.nodes, canvas.edges, data.steps)
    nodes.value = painted.nodes
    edges.value = painted.edges
    void nextTick(() => fitView({ padding: 0.15, maxZoom: 1 }))
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

const stepsByNode = computed(() => new Map((view.data.value?.steps ?? []).filter((s) => s.node_id).map((s) => [s.node_id!, s])))
const waiting = computed(() =>
  nodes.value
    .filter((node) => node.data?.status === 'waiting')
    .map((node) => ({
      id: node.id,
      title: node.data!.label || KINDS[node.data!.kind].title,
      people: tasksOf(node.id)
        .filter((task) => task.state === 'pending' || task.state === 'syncing')
        .map((task) => task.assignee_name),
      due: tasksOf(node.id).find((task) => task.due_at && task.state === 'pending')?.due_at ?? null,
    })),
)
function tasksOf(nodeId: string) {
  return (view.data.value?.tasks ?? []).filter((task) => task.node_id === nodeId)
}
const selected = computed(() => nodes.value.find((node) => node.id === selectedId.value) ?? null)
const selectedStep = computed(() => (selectedId.value ? stepsByNode.value.get(selectedId.value) : undefined))
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
  return DECISION[task.decision] ?? task.decision
}
const modeText = computed(() => {
  const data = view.data.value
  if (!data) return ''
  if (data.mode === 'preview')
    return data.rule_name
      ? `Khi trình, hồ sơ sẽ đi theo quy trình “${data.rule_name}”.`
      : 'Khi trình, hồ sơ đi theo các bước duyệt của biểu mẫu.'
  if (data.mode === 'process') return `Quy trình “${data.rule_name ?? ''}” như lúc trình hồ sơ.`
  return 'Các bước duyệt của biểu mẫu, vẽ dạng sơ đồ.'
})
</script>
<template>
  <section class="card process-canvas-card">
    <header class="card-header">
      <div>
        <h2>Hồ sơ đang ở đâu</h2>
        <small class="muted">{{ modeText }}</small>
      </div>
      <label v-if="(view.data.value?.submissions.length ?? 0) > 1" class="scope-select"
        >Lần trình
        <select v-model="submissionId" aria-label="Chọn lần trình">
          <option value="">Mới nhất</option>
          <option v-for="item in view.data.value?.submissions" :key="item.id" :value="item.id">
            Lần {{ item.number }} · {{ formatDate(item.created_at, true) }}
          </option>
        </select></label
      >
    </header>
    <StatePanel
      v-if="view.isPending.value || view.error.value"
      :loading="view.isPending.value"
      :error="view.error.value"
      compact
      @retry="view.refetch()"
    />
    <template v-else-if="view.data.value">
      <div v-if="view.data.value.outcome" class="process-banner" :class="`outcome-${view.data.value.outcome}`">
        Kết quả: <strong>{{ OUTCOMES[view.data.value.outcome] ?? view.data.value.outcome }}</strong>
      </div>
      <div v-else-if="waiting.length" class="process-banner waiting">
        <Hourglass :size="16" />
        <span>
          <template v-for="(item, index) in waiting" :key="item.id"
            >{{ index ? ' · ' : '' }}Đang chờ <strong>{{ item.title }}</strong
            ><template v-if="item.people.length"> — {{ item.people.join(', ') }}</template
            ><template v-if="item.due"> (hạn {{ formatDate(item.due) }})</template></template
          >
        </span>
      </div>
      <div v-else-if="view.data.value.state === 'failed' || view.data.value.state === 'configuration_error'" class="process-banner failed">
        Quy trình dừng lại, chưa có kết quả. Người quản trị quy trình đã được báo; xem bước đánh dấu lỗi.
      </div>
      <div class="process-canvas">
        <VueFlow
          v-model:nodes="nodes"
          v-model:edges="edges"
          :nodes-draggable="false"
          :nodes-connectable="false"
          :edges-updatable="false"
          :delete-key-code="null"
          :zoom-on-scroll="false"
          :min-zoom="0.3"
          :max-zoom="1.4"
        >
          <template #node-flow="nodeProps"><FlowNode v-bind="nodeProps" /></template>
          <Background :gap="20" :size="1.2" pattern-color="#d4dee6" />
          <Controls position="bottom-left" :show-interactive="false" />
        </VueFlow>
      </div>
      <div class="process-legend" aria-hidden="true">
        <span class="legend done">Đã xong</span><span class="legend wait">Đang chờ</span
        ><span class="legend stop">Dừng / bỏ qua</span><span class="legend fail">Lỗi</span>
        <span class="muted"><MousePointerClick :size="13" /> Bấm một bước để xem chi tiết</span>
      </div>
      <div v-if="selected?.data" class="process-detail">
        <strong>{{ selected.data.label || KINDS[selected.data.kind].title }}</strong>
        <small class="muted">
          {{ KINDS[selected.data.kind].title
          }}<template v-if="selectedStep"> · {{ STATE[selectedStep.state] ?? selectedStep.state }}</template
          ><template v-if="selectedStep?.branch">
            · đi nhánh “{{ branchLabel(selected.data.kind, selectedStep.branch as Branch) }}”</template
          >
        </small>
        <p v-if="selectedStep?.message">{{ selectedStep.message }}</p>
        <p v-if="selectedStep?.total">Đã có {{ selectedStep.answered ?? 0 }}/{{ selectedStep.total }} người trả lời.</p>
        <div v-for="task in tasksOf(selected.id)" :key="task.id" class="list-row">
          <div class="grow">
            <p>
              {{ task.assignee_name }}
              <template v-if="task.decided_by_name && task.decided_by_name !== task.assignee_name"
                >(do {{ task.decided_by_name }} xử lý thay)</template
              >
            </p>
            <small v-if="task.reason">“{{ task.reason }}”</small>
          </div>
          <span class="tag">{{ decisionText(task) || TASK_STATE[task.state] || task.state }}</span>
          <small v-if="task.decided_at" class="muted">{{ formatDate(task.decided_at, true) }}</small>
          <small v-else-if="task.due_at && task.state === 'pending'" class="muted">Hạn {{ formatDate(task.due_at) }}</small>
        </div>
        <p v-if="!selectedStep && view.data.value.mode !== 'preview'" class="muted">Hồ sơ chưa đi qua bước này.</p>
      </div>
    </template>
  </section>
</template>
<style scoped>
.process-canvas {
  height: 440px;
  border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
  background: var(--surface-2);
}
.process-banner {
  display: flex;
  gap: 8px;
  align-items: center;
  margin: 0 18px 12px;
  padding: 10px 12px;
  border-radius: 10px;
  background: var(--surface-2);
}
.process-banner.waiting {
  background: color-mix(in srgb, #d39a2c 14%, transparent);
}
.process-banner.outcome-approved {
  background: var(--green-soft);
  color: var(--green-ink);
}
.process-banner.outcome-rejected,
.process-banner.failed {
  background: var(--red-soft);
  color: var(--red);
}
.process-banner.outcome-needs_revision {
  background: color-mix(in srgb, #d39a2c 14%, transparent);
}
.process-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  align-items: center;
  padding: 10px 18px;
  font-size: 12.5px;
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
.process-detail {
  display: grid;
  gap: 6px;
  padding: 4px 18px 18px;
}
</style>
