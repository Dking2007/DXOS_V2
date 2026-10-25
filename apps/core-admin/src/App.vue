<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import {
  Activity,
  ArrowRight,
  Boxes,
  CheckCircle2,
  ChevronRight,
  CirclePlay,
  Code2,
  Database,
  FileJson2,
  Fingerprint,
  LogOut,
  Plus,
  Save,
  ShieldCheck,
  Workflow,
  XCircle,
} from 'lucide-vue-next'
import {
  ApiError,
  createApi,
  errorText,
  formatDate,
  newIntent,
  queryString,
} from '@dx/web-shared/api.ts'
import type { Page } from '@dx/web-shared/api.ts'
import ModalDialog from '@dx/web-shared/components/ModalDialog.vue'
import StatePanel from '@dx/web-shared/components/StatePanel.vue'
import StatusBadge from '@dx/web-shared/components/StatusBadge.vue'
interface Me {
  subject: string
  display_name: string
  application: string
  roles: string[]
  csrf_token: string
  capabilities: string[]
}
interface Schema {
  id: string
  name: string
  version: number
  revision: number
  state: string
  json_schema: Record<string, unknown>
}
interface GenericRecord {
  id: string
  schema_id: string
  revision: number
  payload: Record<string, unknown>
  resource_id: string
}
interface WorkflowDefinition {
  id: string
  name: string
  state: string
  revision: number
  graph: Record<string, unknown>
}
interface Run {
  id: string
  workflow_id: string
  state: string
  revision: number
  external_key: string
  created_at: string
  input: Record<string, unknown>
  nodes?: {
    id: string
    node_id: string
    state: string
    output?: unknown
    error?: string
  }[]
  human_tasks?: { id: string; state: string; assigned_subject?: string }[]
}
interface Audit {
  id: string
  action: string
  subject?: string
  actor?: string
  resource_id?: string
  created_at: string
}
const api = createApi('core')
const queryClient = useQueryClient()
const me = ref<Me | null>(null)
const authLoading = ref(true)
const authError = ref<unknown>(null)
const section = ref('schemas')
const cursor = ref<string | null>(null)
const selectedSchema = ref<Schema | null>(null)
const selectedWorkflow = ref<WorkflowDefinition | null>(null)
const selectedRunId = ref<string | null>(null)
const tabs = [
  { id: 'schemas', label: 'Schema & bản ghi', icon: Database },
  { id: 'workflows', label: 'Workflow', icon: Workflow },
  { id: 'runs', label: 'Lượt thực thi', icon: Activity },
  { id: 'audit', label: 'Nhật ký hệ thống', icon: ShieldCheck },
]
const enabled = computed(() => !!me.value)
const schemas = useQuery({
  queryKey: ['core', 'schemas'],
  queryFn: () => api.request<Page<Schema>>('/schemas'),
  enabled,
})
const records = useQuery({
  queryKey: computed(() => ['core', 'records', selectedSchema.value?.id]),
  queryFn: () =>
    api.request<Page<GenericRecord>>(
      `/records${queryString({ schema_id: selectedSchema.value?.id })}`,
    ),
  enabled: computed(() => !!selectedSchema.value && !!me.value),
})
const workflows = useQuery({
  queryKey: ['core', 'workflows'],
  queryFn: () => api.request<Page<WorkflowDefinition>>('/workflows'),
  enabled,
})
const runs = useQuery({
  queryKey: computed(() => ['core', 'runs', cursor.value]),
  queryFn: () =>
    api.request<Page<Run>>(
      `/workflow-runs${queryString({ cursor: cursor.value })}`,
    ),
  enabled,
  refetchInterval: 10_000,
})
const runDetail = useQuery({
  queryKey: computed(() => ['core', 'run', selectedRunId.value]),
  queryFn: () => api.request<Run>(`/workflow-runs/${selectedRunId.value}`),
  enabled: computed(() => !!selectedRunId.value && !!me.value),
  refetchInterval: 5_000,
})
const audit = useQuery({
  queryKey: computed(() => ['core', 'audit', cursor.value]),
  queryFn: () =>
    api.request<Page<Audit>>(
      `/audit-logs${queryString({ cursor: cursor.value })}`,
    ),
  enabled: computed(() => !!me.value && section.value === 'audit'),
})
const modal = ref<'schema' | 'record' | 'workflow' | 'run' | 'cancel' | null>(
  null,
)
const name = ref('')
const json = ref('')
const busy = ref(false)
const error = ref<unknown>(null)
const message = ref('')
const intent = ref(newIntent())
const graphExample = JSON.stringify(
  {
    nodes: [
      { id: 'start', type: 'start' },
      { id: 'end', type: 'end' },
    ],
    edges: [{ from: 'start', to: 'end' }],
  },
  null,
  2,
)
const schemaExample = JSON.stringify(
  {
    type: 'object',
    properties: { title: { type: 'string', minLength: 1 } },
    required: ['title'],
    additionalProperties: false,
  },
  null,
  2,
)
const selectedRecord = ref<GenericRecord | null>(null)
const selectedRecordJson = computed(() =>
  selectedRecord.value ? pretty(selectedRecord.value.payload) : '',
)
function pretty(value: unknown) {
  return JSON.stringify(value, null, 2)
}
function reload() {
  window.location.reload()
}
watch(section, () => {
  cursor.value = null
  error.value = null
  message.value = ''
})
onMounted(async () => {
  try {
    me.value = await api.request<Me>('/me')
    api.setCsrf(me.value.csrf_token)
  } catch (cause) {
    if (!(cause instanceof ApiError && cause.status === 401))
      authError.value = cause
  } finally {
    authLoading.value = false
  }
})
async function logout() {
  try {
    await api.request('/auth/logout', { method: 'POST' })
    me.value = null
    queryClient.clear()
  } catch (cause) {
    error.value = cause
  }
}
function open(type: typeof modal.value) {
  modal.value = type
  name.value = ''
  json.value =
    type === 'schema'
      ? schemaExample
      : type === 'workflow'
        ? graphExample
        : '{}'
  error.value = null
  intent.value = newIntent()
}
async function refresh() {
  await queryClient.invalidateQueries({ queryKey: ['core'] })
}
async function save() {
  busy.value = true
  error.value = null
  try {
    let payload: unknown
    if (modal.value !== 'cancel') {
      try {
        payload = JSON.parse(json.value)
      } catch {
        throw new Error(
          'JSON không hợp lệ. Kiểm tra dấu phẩy, dấu ngoặc và tên trường.',
        )
      }
    }
    if (modal.value === 'schema') {
      const item = await api.request<Schema>('/schemas', {
        method: 'POST',
        headers: { 'Idempotency-Key': intent.value },
        body: JSON.stringify({ name: name.value, json_schema: payload }),
      })
      selectedSchema.value = item
    }
    if (modal.value === 'record' && selectedSchema.value)
      await api.request('/records', {
        method: 'POST',
        headers: { 'Idempotency-Key': intent.value },
        body: JSON.stringify({ schema_id: selectedSchema.value.id, payload }),
      })
    if (modal.value === 'workflow') {
      const item = await api.request<WorkflowDefinition>('/workflows', {
        method: 'POST',
        headers: { 'Idempotency-Key': intent.value },
        body: JSON.stringify({ name: name.value, graph: payload }),
      })
      selectedWorkflow.value = item
    }
    if (modal.value === 'run' && selectedWorkflow.value) {
      const item = await api.request<Run>(
        `/workflows/${selectedWorkflow.value.id}/runs`,
        {
          method: 'POST',
          headers: { 'Idempotency-Key': intent.value },
          body: JSON.stringify({ input: payload, external_key: intent.value }),
        },
      )
      selectedRunId.value = item.id
      section.value = 'runs'
    }
    if (modal.value === 'cancel' && runDetail.data.value)
      await api.request(`/workflow-runs/${runDetail.data.value.id}/cancel`, {
        method: 'POST',
        body: JSON.stringify({
          expected_revision: runDetail.data.value.revision,
        }),
      })
    modal.value = null
    message.value = 'Đã ghi nhận thay đổi trên Core.'
    await refresh()
  } catch (cause) {
    error.value = cause
  } finally {
    busy.value = false
  }
}
async function publish(type: 'schema' | 'workflow') {
  const item = type === 'schema' ? selectedSchema.value : selectedWorkflow.value
  if (!item) return
  busy.value = true
  error.value = null
  try {
    if (type === 'schema')
      selectedSchema.value = await api.request<Schema>(
        `/schemas/${item.id}/publish`,
        {
          method: 'POST',
          body: JSON.stringify({ expected_revision: item.revision }),
        },
      )
    else
      selectedWorkflow.value = await api.request<WorkflowDefinition>(
        `/workflows/${item.id}/publish`,
        {
          method: 'POST',
          body: JSON.stringify({ expected_revision: item.revision }),
        },
      )
    message.value = 'Đã phát hành cấu hình bất biến.'
    await refresh()
  } catch (cause) {
    error.value = cause
  } finally {
    busy.value = false
  }
}
async function validate() {
  if (!selectedWorkflow.value) return
  error.value = null
  busy.value = true
  try {
    await api.request(`/workflows/${selectedWorkflow.value.id}/validate`, {
      method: 'POST',
    })
    message.value = 'Đồ thị hợp lệ theo bộ kiểm tra của Core.'
  } catch (cause) {
    error.value = cause
  } finally {
    busy.value = false
  }
}
</script>
<template>
  <main v-if="authLoading || !me" class="card console-login">
    <span class="eyebrow">DX CORE · CONSOLE KỸ THUẬT</span>
    <h1>Nền tảng dùng chung.<br />Độc lập nghiệp vụ.</h1>
    <p>
      Quản lý schema, bản ghi, workflow và lượt thực thi trong application
      namespace của bạn.
    </p>
    <StatePanel
      v-if="authLoading || authError"
      :loading="authLoading"
      :error="authError"
      @retry="reload"
    /><a v-else href="/core/v1/auth/login" class="button"
      >Đăng nhập bằng SSO <ArrowRight :size="17"
    /></a>
    <div class="notice" style="margin-top: 25px">
      <ShieldCheck :size="20" /><span
        >Console không cấp quyền đọc mọi dữ liệu. API kiểm tra namespace và
        quyền tài nguyên ở từng yêu cầu.</span
      >
    </div>
  </main>
  <div v-else class="console-shell">
    <aside class="console-nav">
      <a href="/console/" class="console-logo"
        ><span>D</span>
        <div>Core<small>TECHNICAL CONSOLE</small></div></a
      ><span class="eyebrow" style="color: #8da5b9; padding-left: 13px"
        >NỀN TẢNG</span
      >
      <nav aria-label="Core console">
        <button
          v-for="item in tabs"
          :key="item.id"
          :class="{ active: section === item.id }"
          @click="section = item.id"
        >
          <component :is="item.icon" :size="19" />{{ item.label }}
        </button>
      </nav>
      <div class="console-bottom">
        <p>Core không chứa luật hồ sơ hay phòng ban.</p>
        <a href="/">Mở Desktiny ↗</a>
        <p class="mono" style="margin-top: 15px">API /core/v1 · v0.1</p>
      </div>
    </aside>
    <div class="console-body">
      <header class="console-topbar">
        <div style="display: flex; align-items: center; gap: 17px">
          <strong>Console kỹ thuật</strong
          ><span class="console-context"
            ><Boxes :size="14" />{{ me.application }}</span
          >
        </div>
        <div class="inline-actions">
          <span>{{ me.display_name }}</span
          ><button
            class="icon-button"
            aria-label="Đăng xuất Core console"
            @click="logout"
          >
            <LogOut :size="17" />
          </button>
        </div>
      </header>
      <main class="console-content">
        <header class="page-head">
          <div>
            <span class="eyebrow">APPLICATION / {{ me.application }}</span>
            <h1>{{ tabs.find((item) => item.id === section)?.label }}</h1>
            <p>
              {{
                section === 'schemas'
                  ? 'Hợp đồng dữ liệu có phiên bản, validation và quyền cấp bản ghi.'
                  : section === 'workflows'
                    ? 'Đồ thị tổng quát. Phiên bản bất biến. Trạng thái bền vững.'
                    : section === 'runs'
                      ? 'Theo dõi checkpoint, trạng thái node và các bước đang chờ.'
                      : 'Truy vết tác động nền tảng theo actor và tài nguyên.'
              }}
            </p>
          </div>
          <button
            v-if="section === 'schemas' || section === 'workflows'"
            class="button"
            @click="open(section === 'schemas' ? 'schema' : 'workflow')"
          >
            <Plus :size="17" />{{
              section === 'schemas' ? 'Tạo schema' : 'Tạo workflow'
            }}</button
          ><button v-else class="button secondary" @click="refresh">
            Làm mới
          </button>
        </header>
        <div
          v-if="error && !modal"
          class="notice error console-warning"
          role="alert"
        >
          <div>
            {{ errorText(error)
            }}<code v-if="error instanceof ApiError && error.traceId">{{
              error.traceId
            }}</code>
          </div>
        </div>
        <div
          v-if="message"
          class="notice success console-warning"
          role="status"
        >
          <CheckCircle2 :size="19" />{{ message }}
        </div>
        <div v-if="section === 'schemas'" class="console-columns">
          <section class="card">
            <header class="card-header">
              <h2>Schema registry</h2>
              <FileJson2 :size="18" class="muted" />
            </header>
            <StatePanel
              :loading="schemas.isPending.value"
              :error="schemas.error.value"
              :empty="schemas.data.value?.items.length === 0"
              title="Chưa có schema trong namespace"
              description="Tạo hợp đồng dữ liệu rồi phát hành trước khi ghi record."
              @retry="schemas.refetch()"
            /><button
              v-for="item in schemas.data.value?.items"
              :key="item.id"
              class="console-object"
              :class="{ selected: selectedSchema?.id === item.id }"
              @click="
                () => {
                  selectedSchema = item
                  selectedRecord = null
                }
              "
            >
              <FileJson2 :size="21" class="muted" />
              <div>
                <p>{{ item.name }}</p>
                <small
                  >v{{ item.version }} · r{{ item.revision }} ·
                  <span class="mono">{{ item.id.slice(0, 8) }}</span></small
                >
              </div>
              <StatusBadge :status="item.state" />
            </button>
          </section>
          <div class="stack">
            <section v-if="selectedSchema" class="card">
              <header class="card-header">
                <h2>{{ selectedSchema.name }}</h2>
                <button
                  v-if="selectedSchema.state !== 'published'"
                  class="button small"
                  :disabled="busy"
                  @click="publish('schema')"
                >
                  <CheckCircle2 :size="15" />Phát hành
                </button>
              </header>
              <div class="card-body">
                <pre class="json-output">{{
                  pretty(selectedSchema.json_schema)
                }}</pre>
              </div>
            </section>
            <section v-if="selectedSchema" class="card">
              <header class="card-header">
                <h2>Bản ghi có quyền đọc</h2>
                <button
                  v-if="selectedSchema.state === 'published'"
                  class="button secondary small"
                  @click="open('record')"
                >
                  <Plus :size="15" />Tạo bản ghi
                </button>
              </header>
              <StatePanel
                :loading="records.isPending.value"
                :error="records.error.value"
                :empty="records.data.value?.items.length === 0"
                title="Chưa có bản ghi"
                description="Tạo record theo schema đã phát hành. Dữ liệu được kiểm tra trên API."
                @retry="records.refetch()"
              /><button
                v-for="record in records.data.value?.items"
                :key="record.id"
                class="console-object"
                :class="{ selected: selectedRecord?.id === record.id }"
                @click="selectedRecord = record"
              >
                <Database :size="18" class="muted" />
                <div>
                  <p class="mono">{{ record.id }}</p>
                  <small>Revision {{ record.revision }}</small>
                </div>
                <ChevronRight :size="15" />
              </button>
              <div v-if="selectedRecord" class="card-body">
                <pre class="json-output">{{ selectedRecordJson }}</pre>
              </div>
            </section>
            <div v-if="!selectedSchema" class="card state-panel">
              <Database :size="30" /><strong>Chọn một schema</strong
              ><span
                >Xem cấu trúc và các bản ghi trong application namespace.</span
              >
            </div>
          </div>
        </div>
        <div v-if="section === 'workflows'" class="console-columns">
          <section class="card">
            <header class="card-header">
              <h2>Workflow definitions</h2>
              <Workflow :size="19" class="muted" />
            </header>
            <StatePanel
              :loading="workflows.isPending.value"
              :error="workflows.error.value"
              :empty="workflows.data.value?.items.length === 0"
              title="Chưa có workflow"
              description="Node được hỗ trợ: start, map, if, human_task và end."
              @retry="workflows.refetch()"
            /><button
              v-for="item in workflows.data.value?.items"
              :key="item.id"
              class="console-object"
              :class="{ selected: selectedWorkflow?.id === item.id }"
              @click="selectedWorkflow = item"
            >
              <Workflow :size="22" class="muted" />
              <div>
                <p>{{ item.name }}</p>
                <small class="mono"
                  >{{ item.id.slice(0, 12) }} · r{{ item.revision }}</small
                >
              </div>
              <StatusBadge :status="item.state" />
            </button>
          </section>
          <section v-if="selectedWorkflow" class="card">
            <header class="card-header">
              <h2>{{ selectedWorkflow.name }}</h2>
              <div class="inline-actions">
                <button
                  class="button secondary small"
                  :disabled="busy"
                  @click="validate"
                >
                  Kiểm tra</button
                ><button
                  v-if="selectedWorkflow.state !== 'published'"
                  class="button small"
                  :disabled="busy"
                  @click="publish('workflow')"
                >
                  Phát hành</button
                ><button v-else class="button small" @click="open('run')">
                  <CirclePlay :size="16" />Chạy thủ công
                </button>
              </div>
            </header>
            <div class="card-body">
              <pre class="json-output">{{
                pretty(selectedWorkflow.graph)
              }}</pre>
              <div class="notice" style="margin-top: 20px">
                <Code2 :size="19" /><span
                  >Đồ thị dùng node registry của Core, không chạy
                  Python/JavaScript tùy ý. Human task chỉ được hoàn tất bởi
                  service ứng dụng có quyền.</span
                >
              </div>
            </div>
          </section>
          <div v-else class="card state-panel">
            <Workflow :size="32" /><strong>Chọn một workflow</strong
            ><span>Xem đồ thị, kiểm tra cấu hình và phát hành.</span>
          </div>
        </div>
        <div v-if="section === 'runs'" class="console-columns">
          <section class="card">
            <header class="card-header">
              <h2>Lượt thực thi</h2>
              <Activity :size="19" class="muted" />
            </header>
            <StatePanel
              :loading="runs.isPending.value"
              :error="runs.error.value"
              :empty="runs.data.value?.items.length === 0"
              title="Chưa có lượt thực thi"
              description="Chạy một workflow đã phát hành để kiểm chứng runtime độc lập."
              @retry="runs.refetch()"
            /><button
              v-for="run in runs.data.value?.items"
              :key="run.id"
              class="console-object"
              :class="{ selected: selectedRunId === run.id }"
              @click="selectedRunId = run.id"
            >
              <CirclePlay :size="20" class="muted" />
              <div>
                <p class="mono">{{ run.id.slice(0, 18) }}</p>
                <small>{{ formatDate(run.created_at, true) }}</small>
              </div>
              <StatusBadge :status="run.state" />
            </button>
            <div v-if="runs.data.value?.has_more || cursor" class="pagination">
              <button
                class="button secondary small"
                :disabled="!cursor"
                @click="cursor = null"
              >
                Về đầu</button
              ><button
                class="button secondary small"
                :disabled="!runs.data.value?.has_more"
                @click="cursor = runs.data.value?.next_cursor ?? null"
              >
                Trang tiếp
              </button>
            </div>
          </section>
          <section v-if="selectedRunId" class="card">
            <header class="card-header">
              <h2>Chi tiết thực thi</h2>
              <button
                v-if="
                  runDetail.data.value &&
                  !['succeeded', 'failed', 'cancelled'].includes(
                    runDetail.data.value.state,
                  )
                "
                class="button danger small"
                @click="open('cancel')"
              >
                <XCircle :size="14" />Hủy run
              </button>
            </header>
            <StatePanel
              :loading="runDetail.isPending.value"
              :error="runDetail.error.value"
              @retry="runDetail.refetch()"
            /><template v-if="runDetail.data.value"
              ><div class="card-body">
                <dl class="detail-meta">
                  <div>
                    <dt>Run ID</dt>
                    <dd class="mono">{{ runDetail.data.value.id }}</dd>
                  </div>
                  <div>
                    <dt>Intent</dt>
                    <dd class="mono">
                      {{ runDetail.data.value.external_key }}
                    </dd>
                  </div>
                  <div>
                    <dt>Trạng thái</dt>
                    <dd>
                      <StatusBadge :status="runDetail.data.value.state" />
                    </dd>
                  </div>
                </dl>
              </div>
              <div
                v-for="node in runDetail.data.value.nodes"
                :key="node.id"
                class="workflow-node"
              >
                <span class="file-icon"><Workflow :size="16" /></span>
                <div class="grow">
                  <strong class="mono">{{ node.node_id }}</strong
                  ><small v-if="node.error">{{ node.error }}</small>
                </div>
                <StatusBadge :status="node.state" />
              </div>
              <div class="card-body">
                <span class="section-label">Dữ liệu đầu vào</span>
                <pre class="json-output">{{
                  pretty(runDetail.data.value.input)
                }}</pre>
                <div
                  v-if="runDetail.data.value.human_tasks?.length"
                  class="notice warning"
                  style="margin-top: 18px"
                >
                  Có human task trong run. Quyết định nghiệp vụ phải đi qua ứng
                  dụng sở hữu; console không cung cấp nút duyệt tắt.
                </div>
              </div></template
            >
          </section>
          <div v-else class="card state-panel">
            <Activity :size="32" /><strong>Chọn lượt thực thi</strong
            ><span>Theo dõi các node và trạng thái chờ trên database.</span>
          </div>
        </div>
        <section v-if="section === 'audit'" class="card">
          <header class="card-header">
            <h2>Nhật ký tác động</h2>
            <Fingerprint :size="20" class="muted" />
          </header>
          <StatePanel
            :loading="audit.isPending.value"
            :error="audit.error.value"
            :empty="audit.data.value?.items.length === 0"
            title="Chưa có bản ghi audit"
            @retry="audit.refetch()"
          />
          <div v-if="audit.data.value?.items.length" class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Action</th>
                  <th>Actor</th>
                  <th>Tài nguyên</th>
                  <th>Thời gian</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in audit.data.value.items" :key="item.id">
                  <td class="mono">{{ item.action }}</td>
                  <td class="mono">{{ item.subject || item.actor }}</td>
                  <td class="mono">{{ item.resource_id }}</td>
                  <td class="muted">{{ formatDate(item.created_at, true) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-if="audit.data.value?.has_more || cursor" class="pagination">
            <button
              class="button secondary small"
              :disabled="!cursor"
              @click="cursor = null"
            >
              Về đầu</button
            ><button
              class="button secondary small"
              :disabled="!audit.data.value?.has_more"
              @click="cursor = audit.data.value?.next_cursor ?? null"
            >
              Trang tiếp
            </button>
          </div>
        </section>
      </main>
    </div>
  </div>
  <ModalDialog
    v-if="modal"
    :title="
      modal === 'schema'
        ? 'Tạo schema dữ liệu'
        : modal === 'record'
          ? 'Tạo bản ghi'
          : modal === 'workflow'
            ? 'Tạo workflow tổng quát'
            : modal === 'run'
              ? 'Chạy workflow thủ công'
              : 'Hủy lượt thực thi'
    "
    wide
    @close="
      () => {
        if (!busy) modal = null
      }
    "
    ><div v-if="error" class="notice error error-inline" role="alert">
      {{ errorText(error) }}
    </div>
    <form @submit.prevent="save">
      <div class="stack">
        <div v-if="modal === 'schema' || modal === 'workflow'" class="field">
          <label for="object-name">{{
            modal === 'schema' ? 'Tên schema (key kỹ thuật)' : 'Tên workflow'
          }}</label
          ><input
            id="object-name"
            v-model="name"
            required
            :pattern="
              modal === 'schema' ? '[a-zA-Z][a-zA-Z0-9_.-]*' : undefined
            "
            placeholder="equipment_check"
          />
        </div>
        <div v-if="modal !== 'cancel'" class="field">
          <label for="json-input">{{
            modal === 'schema'
              ? 'JSON Schema · Draft 2020-12'
              : modal === 'workflow'
                ? 'Đồ thị workflow'
                : modal === 'record'
                  ? 'Payload bản ghi'
                  : 'Dữ liệu đầu vào'
          }}</label
          ><textarea
            id="json-input"
            v-model="json"
            class="code-editor"
            required
            spellcheck="false"
            :disabled="busy"
          />
        </div>
        <div v-if="modal === 'run'" class="notice warning">
          Thao tác này tạo intent mới. Workflow có thể tạo tác động thật theo
          node đã cấu hình.
        </div>
        <div v-if="modal === 'cancel'" class="notice warning">
          Hủy sẽ ngăn các bước chưa thực thi. Hệ thống không tự đảo ngược tác
          động đã xảy ra.
        </div>
      </div>
      <div class="form-actions">
        <button
          type="button"
          class="button secondary"
          :disabled="busy"
          @click="modal = null"
        >
          Đóng</button
        ><button class="button" :disabled="busy">
          <Save :size="16" />{{
            busy
              ? 'Đang ghi nhận…'
              : modal === 'run'
                ? 'Tạo lượt thực thi'
                : modal === 'cancel'
                  ? 'Xác nhận hủy run'
                  : 'Lưu cấu hình'
          }}
        </button>
      </div>
    </form></ModalDialog
  >
</template>
