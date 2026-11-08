<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { CheckCircle2, FlaskConical, Play, Plus, Rocket, Sparkles, Trash2, Users, XCircle } from 'lucide-vue-next'
import { ApiError, errorText, formatDate, type Page } from '@dx/web-shared/api.ts'
import type { FormTemplate } from '@dx/web-shared/types.ts'
import ModalDialog from '@dx/web-shared/components/ModalDialog.vue'
import StatePanel from '@dx/web-shared/components/StatePanel.vue'
import { api } from '../api'
import { useAi } from '../ai/useAi'
import { toast } from '../ui/toast'
import { roleLabel } from '../ui/labels'
import { KINDS, OUTCOMES, branchLabel, outputs } from './nodes'
import type { ApiGraph, Branch } from './nodes'

/** What makes a drawn process usable: who may use it, the rehearsal, and publishing it. */
interface ProcessRule {
  id: string
  name: string
  revision: number
  graph: ApiGraph
  form_id: string | null
  allowed_roles: string[] | null
  allowed_department_ids: string[] | null
  required_file_count: number
  active_version_id: string | null
  active_version_no: number | null
  unpublished_changes: boolean
}
interface Version {
  id: string
  version_no: number
  state: string
  created_at: string
}
interface Scenario {
  id: string
  name: string
  payload: Record<string, unknown>
  decisions: Record<string, string>
  file_count: number
  expected_outcome: string | null
  expected_path: string[]
  expected_error_code: string | null
}
interface ScenarioResult {
  scenario_id: string
  name: string
  passed: boolean
  error: string | null
  message?: string
  outcome: string | null
  path: string[]
  people: string[]
}
interface Report {
  id: string
  passed: boolean
  results: ScenarioResult[]
  created_at: string
}
interface Rehearsal {
  error: string | null
  outcome: string | null
  path: string[]
  people: string[]
}
interface Impact {
  version_no: number
  nodes: {
    added: { id: string; label: string; type: string }[]
    removed: { id: string; label: string; type: string }[]
    changed: { id: string; after: { label: string; type: string } }[]
  }
  edges_changed: boolean
  form_changed: boolean
  required_files: { before: number; after: number }
  summary: { scenarios: number; changed: number }
  items: { name: string; changed: boolean; changes: string[]; baseline: Rehearsal; candidate: Rehearsal }[]
}
const ROLES = ['staff', 'manager', 'director', 'technical_admin']
const ERRORS: Record<string, string> = {
  required_documents_missing: 'Thiếu tài liệu bắt buộc',
  form_validation_error: 'Biểu mẫu chưa hợp lệ',
  approver_unresolved: 'Không xác định được người duyệt',
  consultees_missing: 'Không có ai để xin ý kiến',
  assignee_unresolved: 'Không xác định được người xử lý',
  quorum_impossible: 'Không đủ người để đạt số cần đồng ý',
  loop_limit: 'Quay lại bước quá nhiều lần',
}

const props = defineProps<{ ruleId: string; dirty: boolean }>()
const emit = defineEmits<{ close: []; changed: [rule: ProcessRule] }>()
const client = useQueryClient()
const ai = useAi()
const tab = ref<'publish' | 'access' | 'scenarios'>('publish')
const busy = ref(false)
const error = ref('')

const rule = useQuery({
  queryKey: computed(() => ['automation', props.ruleId]),
  queryFn: () => api.request<ProcessRule>(`/automations/${props.ruleId}`),
})
const versions = useQuery({
  queryKey: computed(() => ['process-versions', props.ruleId]),
  queryFn: () => api.request<Page<Version>>(`/processes/${props.ruleId}/versions`),
})
const scenarios = useQuery({
  queryKey: computed(() => ['process-scenarios', props.ruleId]),
  queryFn: () => api.request<Page<Scenario>>(`/processes/${props.ruleId}/scenarios`),
})
const reports = useQuery({
  queryKey: computed(() => ['process-reports', props.ruleId]),
  queryFn: () => api.request<Page<Report>>(`/processes/${props.ruleId}/scenario-reports`),
})
const impact = useQuery({
  queryKey: computed(() => ['process-impact', props.ruleId]),
  queryFn: () => api.request<Impact>(`/processes/${props.ruleId}/impact`),
  enabled: computed(() => !!rule.data.value?.active_version_id),
})
const departments = useQuery({
  queryKey: ['departments'],
  queryFn: () => api.request<Page<{ id: string; name: string }>>('/departments'),
})
const forms = useQuery({
  queryKey: ['forms'],
  queryFn: () => api.request<Page<FormTemplate>>('/forms'),
})
const form = computed(() => forms.data.value?.items.find((item) => item.id === rule.data.value?.form_id))
const latestReport = computed(() => reports.data.value?.items[0])

const roles = ref<string[]>([])
const allowedDepartments = ref<string[]>([])
const requiredFiles = ref(0)
watch(
  () => rule.data.value,
  (value) => {
    if (!value) return
    roles.value = [...(value.allowed_roles ?? [])]
    allowedDepartments.value = [...(value.allowed_department_ids ?? [])]
    requiredFiles.value = value.required_file_count ?? 0
  },
  { immediate: true },
)

async function refresh() {
  await Promise.all(
    [['automation', props.ruleId], ['automations'], ['process-versions', props.ruleId], ['process-impact', props.ruleId],
     ['process-reports', props.ruleId], ['process-scenarios', props.ruleId]].map((queryKey) =>
      client.invalidateQueries({ queryKey }),
    ),
  )
  const latest = await rule.refetch()
  if (latest.data) emit('changed', latest.data)
}
async function act(work: () => Promise<unknown>, message?: string) {
  busy.value = true
  error.value = ''
  try {
    await work()
    if (message) toast.success(message)
    await refresh()
  } catch (cause) {
    // The usual conflict text says to reload, which would not help: the reason is the scenarios.
    error.value = cause instanceof ApiError && cause.code === 'simulation_required' ? cause.message : errorText(cause)
  } finally {
    busy.value = false
  }
}
const send = (path: string, method: string, body?: unknown) =>
  api.request(`/processes/${props.ruleId}${path}`, {
    method,
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  })
const expected = () => ({ expected_revision: rule.data.value!.revision })
const publish = () => act(() => send('/publish', 'POST', expected()), 'Đã phát hành phiên bản mới')
function unpublish() {
  if (!window.confirm('Ngừng áp dụng? Hồ sơ mới sẽ không dùng quy trình này; hồ sơ đã tạo vẫn đi theo phiên bản của mình.'))
    return
  void act(() => send('/unpublish', 'POST', expected()), 'Đã ngừng áp dụng quy trình')
}
const saveAccess = () =>
  act(
    () =>
      send('/settings', 'PUT', {
        ...expected(),
        allowed_roles: roles.value,
        allowed_department_ids: allowedDepartments.value,
        required_file_count: requiredFiles.value,
      }),
    'Đã lưu phân quyền',
  )
const runAll = () => act(() => send('/scenario-reports', 'POST'))
const removeScenario = (id: string) => act(() => send(`/scenarios/${id}`, 'DELETE'))

// ---- A new scenario ----
const blank = () => ({
  name: '',
  answers: {} as Record<string, unknown>,
  decisions: {} as Record<string, string>,
  file_count: 0,
  expected_outcome: 'approved' as string,
})
const adding = ref(false)
const draft = ref(blank())
const branching = computed(() =>
  (rule.data.value?.graph.nodes ?? [])
    .filter((node) => ['approval', 'consult', 'assign_task', 'input', 'acknowledge', 'http_request', 'wait_until'].includes(node.type))
    .map((node) => ({
      id: node.id,
      type: node.type,
      label: node.label || KINDS[node.type].title,
      branches: outputs(node.type, node.data) as Branch[],
    })),
)
const nodeLabel = (id: string) => {
  const node = rule.data.value?.graph.nodes.find((item) => item.id === id)
  return node ? node.label || KINDS[node.type].title : id
}
const outcomeLabel = (value: string | null) =>
  value ? (OUTCOMES[value] ?? value) : 'chưa kết thúc'
const answersFor = () => {
  const values: Record<string, unknown> = {}
  for (const field of form.value?.fields ?? []) {
    const value = draft.value.answers[field.key]
    if (value === undefined || value === '') continue
    values[field.key] = field.type === 'number' ? Number(value) : value
  }
  return values
}
function addScenario() {
  const value = draft.value
  void act(async () => {
    await send('/scenarios', 'POST', {
      name: value.name,
      payload: answersFor(),
      decisions: value.decisions,
      file_count: value.file_count,
      expected_outcome: value.expected_outcome || null,
    })
    adding.value = false
    draft.value = blank()
  })
}
function suggest() {
  void act(async () => {
    const { fixtures } = await api.request<{
      fixtures: (Omit<Scenario, 'id'> & { why: string })[]
    }>(`/ai/processes/${props.ruleId}/scenarios`, { method: 'POST' })
    for (const item of fixtures)
      await send('/scenarios', 'POST', {
        name: item.name,
        payload: item.payload,
        decisions: item.decisions,
        file_count: item.file_count,
        expected_outcome: item.expected_outcome,
        expected_path: item.expected_path,
        expected_error_code: item.expected_error_code,
      })
    toast.success(`AI đề xuất ${fixtures.length} kịch bản; kết quả kỳ vọng lấy theo bản nháp hiện tại, hãy soát lại`)
  })
}
const resultFor = (id: string) => latestReport.value?.results.find((item) => item.scenario_id === id)
</script>
<template>
  <ModalDialog title="Phát hành" wide @close="emit('close')">
    <div class="tabs" role="tablist" aria-label="Phần quản trị quy trình">
      <button class="tab" :class="{ active: tab === 'publish' }" role="tab" :aria-selected="tab === 'publish'" @click="tab = 'publish'">
        <Rocket :size="15" />Phát hành
      </button>
      <button v-if="rule.data.value?.form_id" class="tab" :class="{ active: tab === 'access' }" role="tab" :aria-selected="tab === 'access'" @click="tab = 'access'">
        <Users :size="15" />Phân quyền
      </button>
      <button class="tab" :class="{ active: tab === 'scenarios' }" role="tab" :aria-selected="tab === 'scenarios'" @click="tab = 'scenarios'">
        <FlaskConical :size="15" />Kịch bản thử<span v-if="scenarios.data.value?.items.length" class="tab-count">{{ scenarios.data.value.items.length }}</span>
      </button>
    </div>
    <div v-if="error" class="notice error error-inline" role="alert">{{ error }}</div>
    <StatePanel v-if="!rule.data.value" :loading="rule.isPending.value" :error="rule.error.value" compact @retry="rule.refetch()" />

    <div v-else-if="tab === 'publish'" class="stack">
      <div v-if="dirty" class="notice warning" role="alert">Canvas có thay đổi chưa lưu. Lưu trước khi phát hành.</div>
      <p v-if="rule.data.value.active_version_no">
        Đang áp dụng <strong>phiên bản {{ rule.data.value.active_version_no }}</strong
        >.
        <template v-if="rule.data.value.unpublished_changes">Bản nháp có thay đổi chưa phát hành; hồ sơ mới vẫn theo phiên bản này.</template>
        <template v-else>Bản nháp trùng với phiên bản này.</template>
      </p>
      <p v-else>Đang là bản nháp nên chưa chạy. Phát hành để đưa vào áp dụng.</p>
      <p v-if="scenarios.data.value?.items.length" class="muted">
        Có {{ scenarios.data.value.items.length }} kịch bản thử: tất cả phải đạt trên đúng bản nháp này thì mới phát hành được.
      </p>
      <div class="inline-actions">
        <button
          class="button"
          :disabled="busy || dirty || (!!rule.data.value.active_version_no && !rule.data.value.unpublished_changes)"
          @click="publish"
        >
          <Rocket :size="16" />Phát hành
        </button>
        <button v-if="rule.data.value.active_version_id" class="button secondary" :disabled="busy" @click="unpublish">Ngừng áp dụng</button>
      </div>

      <template v-if="impact.data.value && rule.data.value.unpublished_changes">
        <hr class="divider" />
        <h3>So với phiên bản {{ impact.data.value.version_no }}</h3>
        <ul class="stack" style="margin: 0; padding-left: 18px">
          <li v-for="node in impact.data.value.nodes.added" :key="node.id">Thêm bước “{{ node.label || KINDS[node.type as keyof typeof KINDS]?.title }}”</li>
          <li v-for="node in impact.data.value.nodes.removed" :key="node.id">Bỏ bước “{{ node.label || KINDS[node.type as keyof typeof KINDS]?.title }}”</li>
          <li v-for="node in impact.data.value.nodes.changed" :key="node.id">Đổi cấu hình bước “{{ node.after.label || KINDS[node.after.type as keyof typeof KINDS]?.title }}”</li>
          <li v-if="impact.data.value.edges_changed">Đổi đường nối giữa các bước</li>
          <li v-if="impact.data.value.form_changed">Đổi biểu mẫu</li>
          <li v-if="impact.data.value.required_files.before !== impact.data.value.required_files.after">
            Tài liệu tối thiểu: {{ impact.data.value.required_files.before }} → {{ impact.data.value.required_files.after }}
          </li>
        </ul>
        <p v-if="impact.data.value.summary.scenarios" class="muted">
          {{ impact.data.value.summary.changed }} / {{ impact.data.value.summary.scenarios }} kịch bản thử đổi kết quả.
        </p>
        <div v-for="item in impact.data.value.items.filter((entry) => entry.changed)" :key="item.name" class="list-row">
          <div class="grow">
            <p>{{ item.name }}</p>
            <small class="muted">
              {{ item.baseline.error ? ERRORS[item.baseline.error] ?? item.baseline.error : outcomeLabel(item.baseline.outcome) }}
              →
              {{ item.candidate.error ? ERRORS[item.candidate.error] ?? item.candidate.error : outcomeLabel(item.candidate.outcome) }}
              · {{ item.candidate.path.map(nodeLabel).join(' → ') }}
            </small>
          </div>
        </div>
      </template>

      <template v-if="versions.data.value?.items.length">
        <hr class="divider" />
        <h3>Lịch sử phiên bản</h3>
        <div v-for="version in versions.data.value.items" :key="version.id" class="list-row">
          <div class="grow">
            <p>Phiên bản {{ version.version_no }}</p>
            <small class="muted">{{ formatDate(version.created_at, true) }}</small>
          </div>
          <span class="tag">{{ version.state === 'published' ? 'Đang áp dụng' : 'Đã thay thế' }}</span>
        </div>
      </template>
    </div>

    <form v-else-if="tab === 'access'" class="stack" @submit.prevent="saveAccess">
      <p class="muted">Để trống là không giới hạn. Chọn cả vai trò và phòng ban thì người dùng phải khớp cả hai. Thay đổi có hiệu lực ngay.</p>
      <fieldset class="field">
        <legend>Vai trò được dùng</legend>
        <label v-for="role in ROLES" :key="role" class="check-row">
          <input v-model="roles" type="checkbox" :value="role" />{{ roleLabel(role) }}
        </label>
      </fieldset>
      <fieldset class="field">
        <legend>Phòng ban được dùng</legend>
        <label v-for="item in departments.data.value?.items" :key="item.id" class="check-row">
          <input v-model="allowedDepartments" type="checkbox" :value="item.id" />{{ item.name }}
        </label>
      </fieldset>
      <div class="field">
        <label for="process-files">Số tài liệu tối thiểu khi trình</label>
        <input id="process-files" v-model.number="requiredFiles" type="number" min="0" max="30" />
        <small class="muted">Phần này thuộc nội dung quy trình: áp dụng từ lần phát hành sau.</small>
      </div>
      <div class="form-actions"><button class="button" :disabled="busy">Lưu phân quyền</button></div>
    </form>

    <div v-else class="stack">
      <p class="muted">
        Mỗi kịch bản là một hồ sơ mẫu đi qua bản nháp bằng đúng bộ máy chạy thật, không tạo nhiệm vụ, việc hay thông báo nào.
      </p>
      <div class="inline-actions">
        <button class="button" :disabled="busy || dirty || !scenarios.data.value?.items.length" @click="runAll"><Play :size="15" />Chạy tất cả</button>
        <button class="button secondary" @click="adding = !adding"><Plus :size="15" />Thêm kịch bản</button>
        <button v-if="ai.on('package_scenarios')" class="button secondary" :disabled="busy" @click="suggest"><Sparkles :size="15" />AI đề xuất</button>
      </div>
      <div v-if="dirty" class="notice warning">Canvas có thay đổi chưa lưu; kịch bản chạy trên bản đã lưu.</div>

      <form v-if="adding" class="stack card-body" @submit.prevent="addScenario">
        <div class="form-grid">
          <div class="field">
            <label for="scenario-name">Tên kịch bản<span class="required"> *</span></label>
            <input id="scenario-name" v-model="draft.name" required maxlength="120" placeholder="Kinh phí đúng ngưỡng" />
          </div>
          <div class="field">
            <label for="scenario-files">Số tài liệu</label>
            <input id="scenario-files" v-model.number="draft.file_count" type="number" min="0" max="30" />
          </div>
        </div>
        <div v-if="form?.fields?.length" class="form-grid">
          <div v-for="field in form.fields" :key="field.key" class="field">
            <label :for="`scenario-${field.key}`">{{ field.label }}</label>
            <select v-if="field.options?.length" :id="`scenario-${field.key}`" v-model="draft.answers[field.key]">
              <option value="">—</option>
              <option v-for="option in field.options" :key="option" :value="option">{{ option }}</option>
            </select>
            <input v-else :id="`scenario-${field.key}`" v-model="draft.answers[field.key]" :type="field.type === 'number' ? 'number' : 'text'" />
          </div>
        </div>
        <div v-if="branching.length" class="form-grid">
          <div v-for="node in branching" :key="node.id" class="field">
            <label :for="`scenario-node-${node.id}`">{{ node.label }}</label>
            <select :id="`scenario-node-${node.id}`" v-model="draft.decisions[node.id]">
              <option :value="undefined">Mặc định: {{ node.branches[0] ? branchLabel(node.type, node.branches[0]) : '' }}</option>
              <option v-for="branch in node.branches" :key="branch" :value="branch">{{ branchLabel(node.type, branch) }}</option>
            </select>
          </div>
        </div>
        <div class="field">
          <label for="scenario-outcome">Kết quả mong đợi</label>
          <select id="scenario-outcome" v-model="draft.expected_outcome">
            <option value="approved">Được duyệt</option>
            <option value="rejected">Bị từ chối</option>
            <option value="needs_revision">Cần bổ sung</option>
            <option value="">Chỉ cần đi đến kết thúc</option>
          </select>
        </div>
        <div class="form-actions">
          <button type="button" class="button secondary" @click="adding = false">Hủy</button>
          <button class="button" :disabled="busy">Lưu kịch bản</button>
        </div>
      </form>

      <p v-if="scenarios.data.value && !scenarios.data.value.items.length && !adding" class="muted">
        Chưa có kịch bản nào. Kịch bản không bắt buộc, nhưng giúp phát hiện sai sót trước khi hồ sơ thật đi vào quy trình.
      </p>
      <div v-for="scenario in scenarios.data.value?.items" :key="scenario.id" class="list-row">
        <CheckCircle2 v-if="resultFor(scenario.id)?.passed" :size="18" style="color: var(--success, #1f8a5b)" />
        <XCircle v-else-if="resultFor(scenario.id)" :size="18" style="color: var(--danger, #c0392b)" />
        <FlaskConical v-else :size="18" />
        <div class="grow">
          <p>{{ scenario.name }}</p>
          <small class="muted">
            Mong đợi:
            {{ scenario.expected_error_code ? ERRORS[scenario.expected_error_code] ?? scenario.expected_error_code : scenario.expected_outcome ? outcomeLabel(scenario.expected_outcome) : 'đi đến kết thúc' }}
            <template v-if="resultFor(scenario.id)">
              · Thực tế:
              {{ resultFor(scenario.id)!.error ? ERRORS[resultFor(scenario.id)!.error!] ?? resultFor(scenario.id)!.error : outcomeLabel(resultFor(scenario.id)!.outcome) }}
              <template v-if="resultFor(scenario.id)!.path.length"> · {{ resultFor(scenario.id)!.path.map(nodeLabel).join(' → ') }}</template>
            </template>
          </small>
        </div>
        <button class="icon-button" :aria-label="`Xóa ${scenario.name}`" title="Xóa kịch bản" :disabled="busy" @click="removeScenario(scenario.id)">
          <Trash2 :size="16" />
        </button>
      </div>
    </div>
  </ModalDialog>
</template>
