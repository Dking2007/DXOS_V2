<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<!-- Plugins: install a .zip (or a connected plugin's manifest), approve what each asks for, switch on and
     off, rotate keys, read what was exchanged. A packaged plugin's pages are served by Desktiny and it may
     bring a sector pack, removed with it. Secrets and tokens are shown once, when issued. -->
<script setup lang="ts">
import { computed, ref } from 'vue'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import {
  AlertTriangle,
  Bot,
  Check,
  CheckCircle2,
  Copy,
  FileArchive,
  FileJson,
  Info,
  LayoutPanelLeft,
  MonitorSmartphone,
  PackageOpen,
  Radio,
  Server,
  Workflow,
  KeyRound,
  Activity,
  ListChecks,
  Loader2,
  Power,
  Settings2,
  Puzzle,
  RefreshCw,
  ShieldCheck,
  Trash2,
  Upload,
} from 'lucide-vue-next'
import { api } from '../api'
import { errorText, formatDate } from '@dx/web-shared/api.ts'
import StatePanel from '@dx/web-shared/components/StatePanel.vue'
import ModalDialog from '@dx/web-shared/components/ModalDialog.vue'
import { toast } from '../ui/toast'
import { confirmDialog } from '@dx/web-shared/confirm.ts'

interface Labelled {
  key: string
  label: string
}
interface PluginSummary {
  id: string
  name: string
  version: string
  license: string
  description: string
  base_url: string
  /** A .zip whose pages Desktiny serves itself (no server of its own). */
  packaged: boolean
  permissions: Labelled[]
  events: Labelled[]
  nodes: { kind: string; title: string; description: string }[]
  ui: { slot: string; slot_label: string; title: string }[]
  fields: string[]
  requires: string
  frame_permissions: Labelled[]
  assistant_tools: { name: string; description: string }[]
  host_allowed: boolean
}
interface PackPreview {
  pack: { id: string; name: string; version: string }
  upgrade_from: string | null
  adds: Record<'processes' | 'forms' | 'templates' | 'automations' | 'knowledge', string[]>
  conflicts: string[]
  warnings: string[]
  appearance: unknown
}
interface PluginRow extends PluginSummary {
  state: 'pending' | 'enabled' | 'disabled'
  granted: {
    permissions: string[]
    events: string[]
    fields: string[]
    list_forms: string[]
    frame_permissions: string[]
    assistant_tools?: string[]
  }
  list_form_names: Record<string, string>
  pack: { id: string; name: string; version: string } | null
  files: number
  revision: number
  approved_at: string | null
  updated_at: string
  last_day: Record<string, number>
  health: {
    endpoint: string | null
    checked_at: string | null
    ok: boolean | null
    status_code: number | null
    latency_ms: number | null
    error_rate: number | null
    avg_latency_ms: number | null
  }
  settings_schema: {
    properties: Record<string, { type: 'string' | 'number' | 'boolean'; title: string; description?: string; enum?: string[] | null; secret?: boolean }>
    required: string[]
  }
  settings: { values: Record<string, unknown>; secrets_set: string[]; revision: number }
}
interface Delivery {
  id: string
  kind: 'event' | 'node' | 'api' | 'write' | 'inbound' | 'health' | 'tool'
  event_type: string
  subject: { type: string; id: string } | null
  state: string
  attempts: number
  status_code: number | null
  error: string | null
  created_at: string
}
interface Issued {
  token: string
  secret: string | null
}

const queryClient = useQueryClient()
const listing = useQuery({
  queryKey: ['plugins'],
  queryFn: () => api.request<{ items: PluginRow[]; allowed_hosts: string[] }>('/plugins'),
})
const busy = ref(false)
/** Which action is running (`<plugin id>:<action>`), so only its own button shows the spinner. */
const working = ref('')
function isWorking(row: { id: string }, action: string) {
  return working.value === `${row.id}:${action}`
}
const preview = ref<
  (PluginSummary & { upgrade_from: string | null; files: number; pack_preview: PackPreview | null }) | null
>(null)
const PACK_ADDS = {
  processes: 'Quy trình',
  forms: 'Biểu mẫu',
  templates: 'Mẫu quy trình',
  automations: 'Luồng tự động',
  knowledge: 'Bài kiến thức cho trợ lý AI',
} as const
const previewFile = ref<File | null>(null)
const previewError = ref<unknown>(null)
const approving = ref<PluginRow | null>(null)
const chosen = ref<{
  permissions: string[]
  events: string[]
  fields: string[]
  list_forms: string[]
  frame_permissions: string[]
  assistant_tools: string[]
}>({ permissions: [], events: [], fields: [], list_forms: [], frame_permissions: [], assistant_tools: [] })
// Forms whose dossiers a plugin with cases.list may list: chosen here, at approval.
const forms = useQuery({
  queryKey: ['forms', 'published'],
  queryFn: () => api.request<{ items: { id: string; name: string }[] }>('/forms?limit=200'),
  enabled: computed(() => !!approving.value?.permissions.some((item) => item.key === 'cases.list')),
})
const issued = ref<{ name: string; values: Issued } | null>(null)
const removing = ref<PluginRow | null>(null)
const logOf = ref<PluginRow | null>(null)

const STATE = { pending: 'Chờ duyệt', enabled: 'Đang bật', disabled: 'Đang tắt' }
const KIND = {
  event: 'Sự kiện',
  node: 'Bước quy trình',
  api: 'Đọc API',
  write: 'Ghi API',
  inbound: 'Plugin gửi vào',
  health: 'Kiểm tra sức khoẻ',
  tool: 'Công cụ trợ lý',
}
// The organisation's settings for a plugin; secrets are never shown back, only whether they are set.
const configuring = ref<PluginRow | null>(null)
const draft = ref<Record<string, unknown>>({})
function openSettings(row: PluginRow) {
  configuring.value = row
  draft.value = { ...row.settings.values }
}
/** Required settings still empty (a secret already stored counts as filled). */
const missingSettings = computed(() => {
  const row = configuring.value
  if (!row) return [] as string[]
  return row.settings_schema.required.filter((key) => {
    const field = row.settings_schema.properties[key]
    if (!field || field.type === 'boolean') return false
    if (field.secret && row.settings.secrets_set.includes(key)) return false
    const value = draft.value[key]
    return value === undefined || value === null || String(value).trim() === ''
  })
})
async function saveSettings() {
  const row = configuring.value
  if (!row || busy.value || missingSettings.value.length) return
  busy.value = true
  try {
    // A secret left empty keeps its value; only what was typed is sent.
    const values = Object.fromEntries(
      Object.entries(row.settings_schema.properties)
        .filter(([key, field]) => !field.secret || (draft.value[key] ?? '') !== '')
        .map(([key]) => [key, draft.value[key] ?? null]),
    )
    await api.request(`/plugins/${encodeURIComponent(row.id)}/settings`, {
      method: 'PUT',
      body: JSON.stringify({ expected_revision: row.settings.revision, values }),
    })
    toast.success('Đã lưu cấu hình; plugin được báo có thay đổi.')
    configuring.value = null
    await refresh()
  } catch (cause) {
    toast.error(cause)
  } finally {
    busy.value = false
  }
}
async function checkHealth(row: PluginRow) {
  busy.value = true
  working.value = `${row.id}:health`
  try {
    const result = await api.request<PluginRow>(`/plugins/${encodeURIComponent(row.id)}/health`, { method: 'POST' })
    if (result.health.ok) toast.success(`Plugin trả lời sau ${result.health.latency_ms} ms.`)
    else toast.error('Plugin không trả lời đúng; xem nhật ký.')
    await refresh()
  } catch (cause) {
    toast.error(cause)
  } finally {
    busy.value = false
    working.value = ''
  }
}
const DELIVERY = {
  pending: 'Đang gửi',
  sent: 'Thành công',
  failed: 'Bị từ chối',
  unknown: 'Chưa rõ kết quả',
  cancelled: 'Đã huỷ',
}

const deliveries = useQuery({
  queryKey: computed(() => ['plugin-deliveries', logOf.value?.id]),
  queryFn: () =>
    api.request<{ items: Delivery[] }>(`/plugins/${encodeURIComponent(logOf.value!.id)}/deliveries`),
  enabled: computed(() => !!logOf.value),
  refetchInterval: 10_000,
})

async function refresh() {
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: ['plugins'] }),
    queryClient.invalidateQueries({ queryKey: ['plugin-steps'] }),
    queryClient.invalidateQueries({ queryKey: ['plugin-slots'] }),
  ])
}
function form(file: File) {
  const body = new FormData()
  body.append('file', file)
  return body
}
// Installing goes in three steps: choose the file, read what the plugin asks for, approve it.
const installing = ref(false)
const dragging = ref(false)
const FILE_RULE = 'Chỉ cài được tệp .zip (plugin đóng gói) hoặc .json (bản kê plugin kết nối).'
function openInstall() {
  previewFile.value = null
  preview.value = null
  previewError.value = null
  installing.value = true
}
function closeInstall() {
  if (busy.value) return
  installing.value = false
  previewFile.value = null
}
function chooseAgain() {
  previewFile.value = null
  preview.value = null
  previewError.value = null
}
function onDrop(event: DragEvent) {
  dragging.value = false
  const file = event.dataTransfer?.files?.[0]
  if (file) void choose(file)
}
async function pick(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (file) await choose(file)
}
async function choose(file: File) {
  if (!/\.(zip|json)$/i.test(file.name)) {
    previewError.value = new Error(FILE_RULE)
    previewFile.value = null
    return
  }
  previewFile.value = file
  preview.value = null
  previewError.value = null
  try {
    preview.value = await api.request('/plugins/preview', { method: 'POST', body: form(file) })
  } catch (cause) {
    previewError.value = cause
  }
}
async function install() {
  if (!previewFile.value || busy.value) return
  busy.value = true
  try {
    const row = await api.request<PluginRow & { notes?: string[] }>('/plugins', {
      method: 'POST',
      body: form(previewFile.value),
    })
    toast.success(row.state === 'pending' ? 'Đã cài. Duyệt quyền để bật plugin.' : 'Đã nâng cấp plugin.')
    for (const note of row.notes ?? []) toast.success(note)
    await queryClient.invalidateQueries({ queryKey: ['packs'] })
    previewFile.value = null
    installing.value = false
    await refresh()
    if (row.state === 'pending') openApprove(row)
  } catch (cause) {
    previewError.value = cause
  } finally {
    busy.value = false
  }
}
function openApprove(row: PluginRow) {
  approving.value = row
  chosen.value = {
    permissions: row.permissions.map((item) => item.key),
    events: row.events.map((item) => item.key),
    fields: [...row.fields],
    list_forms: [...(row.granted.list_forms ?? [])],
    frame_permissions: row.frame_permissions.map((item) => item.key),
    assistant_tools: row.assistant_tools.map((tool) => tool.name),
  }
}
// Scopes that change Desktiny's data: shown apart so the approver weighs them.
const WRITE_SCOPES = new Set(['cases.comment', 'cases.fields.write', 'cases.attach', 'tasks.write', 'notifications.send'])
const isWrite = (key: string) => WRITE_SCOPES.has(key)
const previewReads = computed(() => preview.value?.permissions.filter((item) => !isWrite(item.key)) ?? [])
const previewWrites = computed(() => preview.value?.permissions.filter((item) => isWrite(item.key)) ?? [])
const previewAdds = computed(() => {
  const value = preview.value
  if (!value) return []
  return [
    ...value.nodes.map((node) => ({ icon: Workflow, text: `Bước quy trình “${node.title}”` })),
    ...value.ui.map((ui) => ({ icon: LayoutPanelLeft, text: `Khung “${ui.title}” — ${ui.slot_label.toLowerCase()}` })),
    ...value.assistant_tools.map((tool) => ({ icon: Bot, text: `Công cụ trợ lý AI: ${tool.description}` })),
    ...value.frame_permissions.map((item) => ({ icon: MonitorSmartphone, text: `Dùng ${item.label.toLowerCase()}` })),
  ]
})
/** Every choice the approval dialog offers, and how many are ticked. */
const approvalCount = computed(() => {
  const row = approving.value
  if (!row) return { chosen: 0, total: 0 }
  const lists: [string[], string[]][] = [
    [row.permissions.map((item) => item.key), chosen.value.permissions],
    [row.events.map((item) => item.key), chosen.value.events],
    [row.frame_permissions.map((item) => item.key), chosen.value.frame_permissions],
    [row.assistant_tools.map((tool) => tool.name), chosen.value.assistant_tools],
  ]
  if (chosen.value.permissions.includes('cases.fields.write')) lists.push([row.fields, chosen.value.fields])
  return {
    chosen: lists.reduce((sum, [all, picked]) => sum + all.filter((key) => picked.includes(key)).length, 0),
    total: lists.reduce((sum, [all]) => sum + all.length, 0),
  }
})
function setAll(list: string[], keys: string[], on: boolean) {
  const rest = list.filter((key) => !keys.includes(key))
  list.splice(0, list.length, ...rest, ...(on ? keys : []))
}
function toggleIn(list: string[], key: string) {
  const index = list.indexOf(key)
  if (index >= 0) list.splice(index, 1)
  else list.push(key)
}
async function approve() {
  if (!approving.value || busy.value) return
  busy.value = true
  try {
    const result = await api.request<PluginRow & { issued: Issued | null }>(
      `/plugins/${encodeURIComponent(approving.value.id)}/approve`,
      {
        method: 'POST',
        body: JSON.stringify({
          expected_revision: approving.value.revision,
          ...chosen.value,
          // Fields go with the write permission; without it they are not granted.
          fields: chosen.value.permissions.includes('cases.fields.write') ? chosen.value.fields : [],
          list_forms: chosen.value.permissions.includes('cases.list') ? chosen.value.list_forms : [],
        }),
      },
    )
    // A packaged plugin has no server, so nothing is issued to keep.
    if (result.issued) issued.value = { name: result.name, values: result.issued }
    else toast.success('Đã duyệt và bật plugin.')
    approving.value = null
    await refresh()
  } catch (cause) {
    toast.error(cause)
  } finally {
    busy.value = false
  }
}
async function act(row: PluginRow, path: 'enabled' | 'rotate', body: Record<string, unknown> = {}) {
  if (busy.value) return
  if (
    path === 'rotate' &&
    !(await confirmDialog({ message: `Đổi khoá của “${row.name}”? Khoá và token cũ hết hiệu lực ngay; máy chủ plugin cần cập nhật khoá mới.`, confirmLabel: 'Đổi khoá', danger: true }))
  )
    return
  if (
    path === 'enabled' &&
    body.enabled === false &&
    !(await confirmDialog({ message: `Tắt “${row.name}”? Mọi token của plugin hết hiệu lực, khung giao diện và bước quy trình tạm dừng.`, confirmLabel: 'Tắt plugin', danger: true }))
  )
    return
  busy.value = true
  working.value = `${row.id}:${path}`
  try {
    const result = await api.request<PluginRow & { issued?: Issued }>(
      `/plugins/${encodeURIComponent(row.id)}/${path}`,
      { method: 'POST', body: JSON.stringify({ expected_revision: row.revision, ...body }) },
    )
    if (result.issued) issued.value = { name: result.name, values: result.issued }
    else toast.success(result.state === 'enabled' ? 'Đã bật plugin.' : 'Đã tắt plugin; mọi token của nó hết hiệu lực.')
    await refresh()
  } catch (cause) {
    toast.error(cause)
  } finally {
    busy.value = false
    working.value = ''
  }
}
async function remove() {
  if (!removing.value || busy.value) return
  busy.value = true
  try {
    await api.request(`/plugins/${encodeURIComponent(removing.value.id)}`, { method: 'DELETE' })
    toast.success(`Đã gỡ “${removing.value.name}”.`)
    removing.value = null
    await Promise.all([refresh(), queryClient.invalidateQueries({ queryKey: ['packs'] })])
  } catch (cause) {
    toast.error(cause)
  } finally {
    busy.value = false
  }
}
const retrying = ref('')
async function retry(delivery: Delivery) {
  if (retrying.value) return
  retrying.value = delivery.id
  try {
    await api.request(`/plugins/${encodeURIComponent(logOf.value!.id)}/deliveries/${delivery.id}/retry`, {
      method: 'POST',
    })
    toast.success('Đã xếp hàng gửi lại.')
    await deliveries.refetch()
  } catch (cause) {
    toast.error(cause)
  } finally {
    retrying.value = ''
  }
}
// A dialog whose request is still running stays open, so its result is not lost.
function closeUnlessBusy(close: () => void) {
  if (!busy.value) close()
}
async function copy(text: string) {
  try {
    await navigator.clipboard.writeText(text)
    toast.success('Đã sao chép.')
  } catch {
    toast.error('Trình duyệt không cho sao chép; hãy chọn và sao chép thủ công.')
  }
}
</script>
<template>
  <header class="page-head compact">
    <h1 class="sr-only">Plugin</h1>
    <div class="page-actions">
      <button type="button" class="button" :disabled="busy" @click="openInstall"><Upload :size="17" />Cài plugin</button>
    </div>
  </header>
  <StatePanel
    v-if="listing.isPending.value || listing.error.value"
    :loading="listing.isPending.value"
    :error="listing.error.value"
    @retry="listing.refetch()"
  />
  <template v-else-if="listing.data.value">
    <div v-if="!listing.data.value.allowed_hosts.length" class="notice warning plugin-hosts">
      <AlertTriangle :size="18" /><span
        >Triển khai chưa cho phép máy chủ plugin nào. Bộ phận kỹ thuật cần khai tên máy chủ của plugin trong
        <code>PLUGIN_ALLOWED_HOSTS</code> (và địa chỉ của nó trong <code>PLUGIN_FRAME_SOURCES</code> nếu plugin có khung
        giao diện).</span
      >
    </div>
    <p v-else class="muted plugin-hosts">
      Máy chủ plugin được phép: <code>{{ listing.data.value.allowed_hosts.join(', ') }}</code>
    </p>
    <section class="card">
      <StatePanel
        v-if="!listing.data.value.items.length"
        :empty="true"
        title="Chưa có plugin"
        description="Plugin là ứng dụng chạy ở máy chủ riêng, kết nối qua sự kiện, API có phạm vi, bước quy trình và khung giao diện cách ly."
      />
      <article v-for="row in listing.data.value.items" :key="row.id" class="plugin-row">
        <span class="plugin-icon" :class="row.state"><Puzzle :size="20" /></span>
        <div class="grow">
          <div class="plugin-title">
            <strong>{{ row.name }}</strong>
            <span class="tag" :class="`state-${row.state}`">{{ STATE[row.state] }}</span>
            <span v-if="row.packaged" class="tag">Đóng gói</span>
            <span v-if="!row.host_allowed" class="tag state-bad">Máy chủ chưa được phép</span>
          </div>
          <small class="muted mono"
            >{{ row.id }} · {{ row.version }} · {{ row.packaged ? `${row.files} tệp giao diện` : row.base_url }}</small
          >
          <p v-if="row.description">{{ row.description }}</p>
          <ul class="plugin-facts">
            <li v-if="row.permissions.length">
              <strong>Quyền:</strong>
              <span
                v-for="item in row.permissions"
                :key="item.key"
                class="chip"
                :class="{ off: !row.granted.permissions.includes(item.key) }"
                :title="item.label"
                >{{ item.label }}</span
              >
            </li>
            <li v-if="row.events.length">
              <strong>Sự kiện:</strong>
              <span
                v-for="item in row.events"
                :key="item.key"
                class="chip"
                :class="{ off: !row.granted.events.includes(item.key) }"
                >{{ item.label }}</span
              >
            </li>
            <li v-if="row.fields.length">
              <strong>Trường được ghi:</strong>
              <span
                v-for="key in row.fields"
                :key="key"
                class="chip mono"
                :class="{ off: !row.granted.fields.includes(key) }"
                >{{ key }}</span
              >
            </li>
            <li v-if="Object.keys(row.list_form_names ?? {}).length">
              <strong>Được liệt kê hồ sơ của:</strong> {{ Object.values(row.list_form_names).join(', ') }}
            </li>
            <li v-if="row.pack">
              <strong>Gói giao diện đi kèm:</strong> {{ row.pack.name }} ({{ row.pack.version }})
            </li>
            <li v-if="row.nodes.length">
              <strong>Bước quy trình:</strong> {{ row.nodes.map((n) => n.title).join(', ') }}
            </li>
            <li v-if="row.ui.length">
              <strong>Khung giao diện:</strong> {{ row.ui.map((u) => `${u.title} (${u.slot_label})`).join(', ') }}
            </li>
            <li v-if="row.assistant_tools.length">
              <strong>Công cụ cho trợ lý AI:</strong>
              <span
                v-for="tool in row.assistant_tools"
                :key="tool.name"
                class="chip"
                :class="{ off: !row.granted.assistant_tools?.includes(tool.name) }"
                :title="tool.description"
                >{{ tool.name }}</span
              >
            </li>
            <li v-if="row.frame_permissions.length">
              <strong>Quyền thiết bị:</strong>
              <span
                v-for="item in row.frame_permissions"
                :key="item.key"
                class="chip"
                :class="{ off: !row.granted.frame_permissions?.includes(item.key) }"
                >{{ item.label }}</span
              >
            </li>
            <li v-if="row.state !== 'pending'" class="muted">
              24 giờ qua: {{ row.last_day.sent ?? 0 }} lần thành công<template v-if="row.last_day.failed">
                · <span class="overdue-text">{{ row.last_day.failed }} bị từ chối</span></template
              ><template v-if="row.last_day.pending"> · {{ row.last_day.pending }} đang gửi</template>
            </li>
            <li v-if="row.state !== 'pending' && (row.health.checked_at || row.health.error_rate !== null)" class="muted">
              <template v-if="row.health.checked_at"
                >Sức khoẻ:
                <span :class="row.health.ok ? '' : 'overdue-text'">{{ row.health.ok ? 'tốt' : 'lỗi' }}</span>
                ({{ formatDate(row.health.checked_at, true) }})</template
              ><template v-if="row.health.error_rate !== null">
                · tỉ lệ lỗi 24 giờ {{ Math.round(row.health.error_rate * 100) }}%</template
              ><template v-if="row.health.avg_latency_ms !== null"> · trả lời trung bình {{ row.health.avg_latency_ms }} ms</template>
            </li>
          </ul>
        </div>
        <div class="plugin-actions">
          <button v-if="row.state === 'pending'" class="button small" :disabled="busy" @click="openApprove(row)">
            <ShieldCheck :size="15" />Duyệt quyền
          </button>
          <button
            v-else
            class="button secondary small"
            :disabled="busy || (row.state !== 'enabled' && !row.host_allowed)"
            :title="row.state !== 'enabled' && !row.host_allowed ? 'Máy chủ plugin chưa được phép; không bật được' : ''"
            :aria-busy="isWorking(row, 'enabled')"
            @click="act(row, 'enabled', { enabled: row.state !== 'enabled' })"
          >
            <Loader2 v-if="isWorking(row, 'enabled')" :size="15" class="spin" /><Power v-else :size="15" />{{
              isWorking(row, 'enabled') ? (row.state === 'enabled' ? 'Đang tắt…' : 'Đang bật…') : row.state === 'enabled' ? 'Tắt' : 'Bật'
            }}
          </button>
          <button v-if="row.state !== 'pending'" class="button ghost small" :disabled="busy" @click="openApprove(row)">
            <ShieldCheck :size="15" />Quyền
          </button>
          <button
            v-if="row.state !== 'pending' && !row.packaged"
            class="button ghost small"
            :disabled="busy"
            :aria-busy="isWorking(row, 'rotate')"
            @click="act(row, 'rotate')"
          >
            <Loader2 v-if="isWorking(row, 'rotate')" :size="15" class="spin" /><KeyRound v-else :size="15" />{{
              isWorking(row, 'rotate') ? 'Đang đổi…' : 'Đổi khoá'
            }}
          </button>
          <RouterLink
            v-for="(page, index) in row.state === 'enabled' ? row.ui : []"
            v-show="page.slot === 'admin.page'"
            :key="`admin-${index}`"
            class="button ghost small"
            :to="`/plugins/${encodeURIComponent(row.id)}/admin/${index}`"
            ><Puzzle :size="15" />{{ page.title }}</RouterLink
          >
          <button
            v-if="Object.keys(row.settings_schema.properties).length"
            class="button ghost small"
            :disabled="busy"
            @click="openSettings(row)"
          >
            <Settings2 :size="15" />Cấu hình
          </button>
          <button
            v-if="row.health.endpoint"
            class="button ghost small"
            :disabled="busy"
            :aria-busy="isWorking(row, 'health')"
            title="Gọi thử điểm kiểm tra sức khoẻ của plugin"
            @click="checkHealth(row)"
          >
            <Loader2 v-if="isWorking(row, 'health')" :size="15" class="spin" /><Activity v-else :size="15" />{{
              isWorking(row, 'health') ? 'Đang kiểm tra…' : 'Kiểm tra'
            }}
          </button>
          <button class="button ghost small" @click="logOf = row"><ListChecks :size="15" />Nhật ký</button>
          <button class="button ghost small plugin-remove" :disabled="busy" @click="removing = row"><Trash2 :size="15" />Gỡ</button>
        </div>
      </article>
    </section>
    <p class="muted plugin-footnote">
      Trang của plugin chạy trong khung cách ly, không đọc được phiên hay dữ liệu của Desktiny. Sự kiện và lời gọi bước
      quy trình được ký HMAC; plugin chỉ đọc được hồ sơ nó đã được báo, hoặc theo quyền của người đang xem khung. Cách
      viết plugin: <code>docs/plugins.md</code>.
    </p>
  </template>

  <ModalDialog v-if="installing" :title="preview?.upgrade_from ? 'Nâng cấp plugin' : 'Cài plugin'" wide @close="closeInstall">
    <ol class="install-steps" aria-label="Các bước cài plugin">
      <li :class="previewFile ? 'done' : 'current'" :aria-current="previewFile ? undefined : 'step'">
        <span><Check v-if="previewFile" :size="13" /><template v-else>1</template></span>Chọn tệp
      </li>
      <li :class="previewFile ? 'current' : ''" :aria-current="previewFile ? 'step' : undefined"><span>2</span>Xem trước</li>
      <li><span>3</span>Duyệt quyền</li>
    </ol>

    <template v-if="!previewFile">
      <div v-if="previewError" class="notice error" role="alert"><AlertTriangle :size="18" /><span>{{ errorText(previewError) }}</span></div>
      <label
        class="install-drop"
        :class="{ dragging }"
        @dragenter.prevent="dragging = true"
        @dragover.prevent="dragging = true"
        @dragleave.prevent="dragging = false"
        @drop.prevent="onDrop"
      >
        <span class="install-drop-icon"><Upload :size="24" /></span>
        <strong>Kéo thả tệp plugin vào đây</strong>
        <span class="muted">hoặc <span class="install-drop-link">chọn tệp từ máy</span> · .zip hoặc .json, tối đa 10 MB</span>
        <input
          type="file"
          accept=".json,.zip,application/json,application/zip"
          class="sr-only"
          @change="pick"
        />
      </label>
      <div class="install-kinds">
        <div class="install-kind">
          <span class="install-kind-icon"><FileArchive :size="18" /></span>
          <div>
            <strong>Plugin đóng gói (.zip)</strong>
            <p class="muted">Trang giao diện nằm trong gói, Desktiny tự phục vụ; có thể kèm gói giao diện. Không cần máy chủ riêng.</p>
          </div>
        </div>
        <div class="install-kind">
          <span class="install-kind-icon"><FileJson :size="18" /></span>
          <div>
            <strong>Plugin kết nối (.json hoặc .zip)</strong>
            <p class="muted">Ứng dụng chạy ở máy chủ của cơ quan; máy chủ phải có trong <code>PLUGIN_ALLOWED_HOSTS</code>.</p>
          </div>
        </div>
      </div>
      <p class="install-note muted"><ShieldCheck :size="15" />Cài xong plugin ở trạng thái chờ duyệt và chưa làm được gì cho tới khi bạn duyệt quyền.</p>
    </template>

    <template v-else>
      <div v-if="previewError" class="notice error" role="alert"><AlertTriangle :size="18" /><span>{{ errorText(previewError) }}</span></div>
      <div v-if="!preview && !previewError" class="install-loading"><Loader2 :size="20" class="spin" />Đang đọc {{ previewFile.name }}…</div>
      <div v-if="!preview && previewError" class="form-actions">
        <button type="button" class="button secondary" @click="chooseAgain">Chọn tệp khác</button>
      </div>

      <div v-if="preview" class="install-preview">
        <header class="install-head">
          <span class="install-head-icon"><Puzzle :size="24" /></span>
          <div class="install-head-text">
            <h3>{{ preview.name }}</h3>
            <div class="install-badges">
              <span class="tag">
                <template v-if="preview.upgrade_from">{{ preview.upgrade_from }} → </template>{{ preview.version }}
              </span>
              <span class="tag" :class="preview.packaged ? 'kind-packaged' : 'kind-connected'">
                <component :is="preview.packaged ? PackageOpen : Server" :size="12" />{{ preview.packaged ? 'Đóng gói' : 'Kết nối' }}
              </span>
              <span class="tag">{{ preview.license }}</span>
            </div>
            <small class="muted mono">{{ preview.id }}</small>
          </div>
        </header>
        <p v-if="preview.description" class="install-desc">{{ preview.description }}</p>
        <div class="install-source">
          <template v-if="preview.packaged"
            ><PackageOpen :size="15" />Desktiny tự phục vụ {{ preview.files ? `${preview.files} tệp` : 'các trang' }} giao diện
            trong gói; không cần máy chủ riêng.</template
          >
          <template v-else><Server :size="15" />Máy chủ: <code>{{ preview.base_url }}</code></template>
        </div>
        <div v-if="!preview.host_allowed" class="notice error" role="alert">
          <AlertTriangle :size="18" /><span>Máy chủ của plugin chưa có trong <code>PLUGIN_ALLOWED_HOSTS</code>; nhờ bộ phận kỹ thuật thêm vào rồi cài lại.</span>
        </div>

        <div class="install-grid">
          <section class="install-section">
            <h4><ShieldCheck :size="16" />Quyền xin cấp</h4>
            <p v-if="!preview.permissions.length" class="muted">Không xin quyền dữ liệu nào.</p>
            <ul class="install-list">
              <li v-for="item in previewReads" :key="item.key"><span class="scope read">Đọc</span>{{ item.label }}</li>
              <li v-for="item in previewWrites" :key="item.key"><span class="scope write">Ghi</span>{{ item.label }}</li>
            </ul>
            <div v-if="preview.fields.length" class="install-fields">
              <small class="muted">Trường được ghi:</small>
              <code v-for="key in preview.fields" :key="key">{{ key }}</code>
            </div>
          </section>
          <section class="install-section">
            <h4><LayoutPanelLeft :size="16" />Thêm vào Desktiny</h4>
            <p v-if="!previewAdds.length" class="muted">Không thêm khung hay bước nào.</p>
            <ul class="install-list">
              <li v-for="(item, index) in previewAdds" :key="index"><component :is="item.icon" :size="15" class="install-li-icon" />{{ item.text }}</li>
            </ul>
          </section>
          <section v-if="preview.events.length" class="install-section">
            <h4><Radio :size="16" />Sự kiện plugin nhận</h4>
            <div class="install-chips">
              <span v-for="item in preview.events" :key="item.key" class="chip">{{ item.label }}</span>
            </div>
            <small class="muted">Chỉ gửi mã bản ghi, không gửi nội dung; mọi lần gửi đều có chữ ký.</small>
          </section>
          <section v-if="preview.pack_preview" class="install-section">
            <h4>
              <PackageOpen :size="16" />Gói giao diện đi kèm: {{ preview.pack_preview.pack.name }}
              <span class="tag"><template v-if="preview.pack_preview.upgrade_from">{{ preview.pack_preview.upgrade_from }} → </template>{{ preview.pack_preview.pack.version }}</span>
            </h4>
            <ul class="install-list">
              <template v-for="(label, key) in PACK_ADDS" :key="key">
                <li v-if="preview.pack_preview.adds[key]?.length"><CheckCircle2 :size="15" class="install-li-icon" />{{ label }}: {{ preview.pack_preview.adds[key].join(', ') }}</li>
              </template>
              <li v-if="preview.pack_preview.appearance"><CheckCircle2 :size="15" class="install-li-icon" />Giao diện riêng (chọn dùng ở Quản trị › Gói giao diện)</li>
            </ul>
            <div v-for="item in preview.pack_preview.conflicts" :key="item" class="notice warning"><AlertTriangle :size="16" /><span>{{ item }}</span></div>
            <small v-for="item in preview.pack_preview.warnings" :key="item" class="muted">{{ item }}</small>
            <small class="muted">Gói được cài và gỡ cùng plugin.</small>
          </section>
        </div>
        <p class="install-note muted"><Info :size="15" />Cài xong, bạn chọn cấp từng quyền ở bước tiếp theo; plugin chưa làm được gì cho tới khi được duyệt.</p>
      </div>

      <div v-if="preview" class="form-actions install-actions">
        <button type="button" class="button ghost" :disabled="busy" @click="chooseAgain">Chọn tệp khác</button>
        <span class="grow" />
        <button type="button" class="button secondary" :disabled="busy" @click="closeInstall">Huỷ</button
        ><button
          type="button"
          class="button"
          :disabled="busy || !preview.host_allowed"
          :title="preview.host_allowed ? '' : 'Máy chủ của plugin chưa được phép'"
          :aria-busy="busy"
          @click="install"
        >
          <Loader2 v-if="busy" :size="16" class="spin" />{{
            busy ? (preview.upgrade_from ? 'Đang nâng cấp…' : 'Đang cài…') : preview.upgrade_from ? 'Nâng cấp' : 'Cài và duyệt quyền'
          }}
        </button>
      </div>
    </template>
  </ModalDialog>

  <ModalDialog
    v-if="approving"
    :title="`Duyệt quyền: ${approving.name}`"
    wide
    @close="closeUnlessBusy(() => (approving = null))"
  >
    <ol v-if="approving.state === 'pending'" class="install-steps" aria-label="Các bước cài plugin">
      <li class="done"><span><Check :size="13" /></span>Chọn tệp</li>
      <li class="done"><span><Check :size="13" /></span>Xem trước</li>
      <li class="current" aria-current="step"><span>3</span>Duyệt quyền</li>
    </ol>
    <div class="approve-summary">
      <p class="muted">Chỉ cấp những gì plugin thật sự cần; mục bỏ chọn thì plugin không có. Đổi lại được bất cứ lúc nào ở nút “Quyền”.</p>
      <span class="approve-count" aria-live="polite">Cấp {{ approvalCount.chosen }}/{{ approvalCount.total }}</span>
    </div>

    <div class="approve-groups">
      <section v-if="approving.permissions.length" class="approve-group">
        <header>
          <h4><ShieldCheck :size="16" />Quyền dữ liệu</h4>
          <button
            type="button"
            class="button ghost small"
            @click="setAll(chosen.permissions, approving.permissions.map((i) => i.key), chosen.permissions.length < approving.permissions.length)"
          >
            {{ chosen.permissions.length < approving.permissions.length ? 'Chọn tất cả' : 'Bỏ chọn' }}
          </button>
        </header>
        <label v-for="item in approving.permissions" :key="item.key" class="approve-item" :class="{ write: isWrite(item.key) }"
          ><input type="checkbox" :checked="chosen.permissions.includes(item.key)" @change="toggleIn(chosen.permissions, item.key)" />
          <span class="approve-text">{{ item.label }}<code>{{ item.key }}</code></span>
          <span class="scope" :class="isWrite(item.key) ? 'write' : 'read'">{{ isWrite(item.key) ? 'Ghi' : 'Đọc' }}</span></label
        >
        <p v-if="approving.permissions.some((i) => isWrite(i.key) && chosen.permissions.includes(i.key))" class="approve-hint">
          <AlertTriangle :size="14" />Quyền ghi để plugin thay đổi dữ liệu; mỗi lần ghi đều có tên plugin trong lịch sử.
        </p>
      </section>

      <section v-if="approving.fields.length && chosen.permissions.includes('cases.fields.write')" class="approve-group">
        <header>
          <h4>Trường biểu mẫu được ghi</h4>
          <button type="button" class="button ghost small" @click="setAll(chosen.fields, approving.fields, chosen.fields.length < approving.fields.length)">
            {{ chosen.fields.length < approving.fields.length ? 'Chọn tất cả' : 'Bỏ chọn' }}
          </button>
        </header>
        <div class="approve-chips">
          <label v-for="key in approving.fields" :key="key" class="approve-chip" :class="{ on: chosen.fields.includes(key) }"
            ><input type="checkbox" class="sr-only" :checked="chosen.fields.includes(key)" @change="toggleIn(chosen.fields, key)" /><Check
              v-if="chosen.fields.includes(key)"
              :size="13"
            /><code>{{ key }}</code></label
          >
        </div>
      </section>

      <section v-if="chosen.permissions.includes('cases.list')" class="approve-group">
        <header><h4>Quy trình được liệt kê hồ sơ</h4></header>
        <p v-if="forms.isPending.value" class="muted">Đang tải quy trình…</p>
        <label v-for="item in forms.data.value?.items ?? []" :key="item.id" class="approve-item"
          ><input type="checkbox" :checked="chosen.list_forms.includes(item.id)" @change="toggleIn(chosen.list_forms, item.id)" /><span
            class="approve-text"
            >{{ item.name }}</span
          ></label
        >
        <small class="muted">Plugin chỉ liệt kê (và đọc) hồ sơ của quy trình được chọn; không chọn thì không thấy hồ sơ nào.</small>
      </section>

      <section v-if="approving.events.length" class="approve-group">
        <header>
          <h4><Radio :size="16" />Sự kiện được gửi</h4>
          <button
            type="button"
            class="button ghost small"
            @click="setAll(chosen.events, approving.events.map((i) => i.key), chosen.events.length < approving.events.length)"
          >
            {{ chosen.events.length < approving.events.length ? 'Chọn tất cả' : 'Bỏ chọn' }}
          </button>
        </header>
        <label v-for="item in approving.events" :key="item.key" class="approve-item"
          ><input type="checkbox" :checked="chosen.events.includes(item.key)" @change="toggleIn(chosen.events, item.key)" /><span
            class="approve-text"
            >{{ item.label }}<code>{{ item.key }}</code></span
          ></label
        >
      </section>

      <section v-if="approving.frame_permissions.length" class="approve-group">
        <header><h4><MonitorSmartphone :size="16" />Quyền thiết bị cho khung giao diện</h4></header>
        <label v-for="item in approving.frame_permissions" :key="item.key" class="approve-item"
          ><input
            type="checkbox"
            :checked="chosen.frame_permissions.includes(item.key)"
            @change="toggleIn(chosen.frame_permissions, item.key)"
          /><span class="approve-text">{{ item.label }}</span></label
        >
        <small class="muted">Trình duyệt vẫn hỏi người dùng trước khi cho dùng.</small>
      </section>

      <section v-if="approving.assistant_tools.length" class="approve-group">
        <header><h4><Bot :size="16" />Công cụ cho trợ lý AI</h4></header>
        <label v-for="tool in approving.assistant_tools" :key="tool.name" class="approve-item"
          ><input
            type="checkbox"
            :checked="chosen.assistant_tools.includes(tool.name)"
            @change="toggleIn(chosen.assistant_tools, tool.name)"
          /><span class="approve-text">{{ tool.description }}<code>{{ tool.name }}</code></span></label
        >
        <small class="muted">Chỉ đọc, theo quyền của người hỏi; dùng khi “Trợ lý dùng công cụ của plugin” bật ở Cài đặt AI.</small>
      </section>
    </div>

    <div class="form-actions">
      <button type="button" class="button secondary" :disabled="busy" @click="approving = null">Để sau</button
      ><button type="button" class="button" :disabled="busy" :aria-busy="busy" @click="approve">
        <Loader2 v-if="busy" :size="16" class="spin" /><ShieldCheck v-else :size="16" />{{ busy ? 'Đang duyệt…' : 'Duyệt và bật' }}
      </button>
    </div>
  </ModalDialog>

  <ModalDialog v-if="configuring" :title="`Cấu hình: ${configuring.name}`" @close="closeUnlessBusy(() => (configuring = null))">
    <form class="stack" @submit.prevent="saveSettings">
      <p class="muted">Giá trị dành cho cơ quan này. Ô bí mật được mã hoá khi lưu và không hiện lại.</p>
      <div v-for="(field, key) in configuring.settings_schema.properties" :key="key" class="field">
        <label v-if="field.type !== 'boolean'" :for="`setting-${key}`"
          >{{ field.title
          }}<span v-if="configuring.settings_schema.required.includes(String(key))" class="required"> *</span></label
        >
        <select v-if="field.enum?.length" :id="`setting-${key}`" v-model="draft[key]">
          <option :value="null">Chọn…</option>
          <option v-for="option in field.enum" :key="option" :value="option">{{ option }}</option>
        </select>
        <label v-else-if="field.type === 'boolean'" class="checkbox-label"
          ><input v-model="draft[key]" type="checkbox" />{{ field.title }}</label
        >
        <input
          v-else-if="field.type === 'number'"
          :id="`setting-${key}`"
          v-model.number="draft[key]"
          type="number"
          :aria-required="configuring.settings_schema.required.includes(String(key))"
        />
        <input
          v-else
          :id="`setting-${key}`"
          v-model="draft[key]"
          :type="field.secret ? 'password' : 'text'"
          autocomplete="off"
          :aria-required="configuring.settings_schema.required.includes(String(key))"
          :placeholder="
            field.secret && configuring.settings.secrets_set.includes(String(key)) ? 'Đã đặt; để trống để giữ' : ''
          "
        />
        <small v-if="field.description">{{ field.description }}</small>
      </div>
      <div class="form-actions">
        <button type="button" class="button secondary" :disabled="busy" @click="configuring = null">Huỷ</button
        ><button
          type="submit"
          class="button"
          :disabled="busy || missingSettings.length > 0"
          :title="missingSettings.length ? 'Điền các ô bắt buộc (*) trước khi lưu' : ''"
          :aria-busy="busy"
        >
          <Loader2 v-if="busy" :size="16" class="spin" />{{ busy ? 'Đang lưu…' : 'Lưu cấu hình' }}
        </button>
      </div>
    </form>
  </ModalDialog>

  <ModalDialog v-if="issued" :title="`Khoá cho ${issued.name}`" @close="issued = null">
    <div class="stack">
      <div class="notice warning">
        <AlertTriangle :size="18" /><span
          >Chỉ hiện <strong>một lần</strong>. Đưa vào cấu hình máy chủ plugin ngay; mất thì bấm “Đổi khoá” để cấp
          lại.</span
        >
      </div>
      <div v-if="issued.values.secret" class="field">
        <label>Khoá ký (kiểm chữ ký sự kiện và bước quy trình)</label>
        <div class="plugin-secret">
          <code>{{ issued.values.secret }}</code
          ><button class="icon-button" type="button" aria-label="Sao chép khoá ký" title="Sao chép" @click="copy(issued.values.secret!)">
            <Copy :size="15" />
          </button>
        </div>
      </div>
      <div class="field">
        <label>Token gọi API plugin</label>
        <div class="plugin-secret">
          <code>{{ issued.values.token }}</code
          ><button class="icon-button" type="button" aria-label="Sao chép token" title="Sao chép" @click="copy(issued.values.token)">
            <Copy :size="15" />
          </button>
        </div>
      </div>
      <div class="form-actions">
        <button type="button" class="button" @click="issued = null">Đã lưu</button>
      </div>
    </div>
  </ModalDialog>

  <ModalDialog v-if="removing" title="Gỡ plugin" @close="closeUnlessBusy(() => (removing = null))">
    <div class="stack">
      <p>
        Gỡ <strong>{{ removing.name }}</strong>? Mọi token của plugin hết hiệu lực ngay; khung giao diện biến mất; bước
        quy trình của plugin sẽ báo lỗi và dừng có lý do cho tới khi được thay.
      </p>
      <p v-if="removing.pack">
        Gói giao diện đi kèm <strong>{{ removing.pack.name }}</strong> cũng được gỡ: quy trình chưa có hồ sơ bị xoá, quy trình
        đã có hồ sơ chỉ ngừng sử dụng.
      </p>
      <div class="form-actions">
        <button type="button" class="button secondary" :disabled="busy" @click="removing = null">Huỷ</button
        ><button type="button" class="button danger" :disabled="busy" :aria-busy="busy" @click="remove">
          <Loader2 v-if="busy" :size="16" class="spin" />{{ busy ? 'Đang gỡ…' : 'Gỡ plugin' }}
        </button>
      </div>
    </div>
  </ModalDialog>

  <ModalDialog v-if="logOf" :title="`Nhật ký: ${logOf.name}`" wide @close="logOf = null">
    <StatePanel
      v-if="deliveries.isPending.value || deliveries.error.value || !deliveries.data.value?.items.length"
      :loading="deliveries.isPending.value"
      :error="deliveries.error.value"
      :empty="true"
      title="Chưa có trao đổi nào"
      description="Sự kiện, lời gọi API và bước quy trình của plugin sẽ được ghi tại đây."
      @retry="deliveries.refetch()"
    />
    <div v-else class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Lúc</th>
            <th>Loại</th>
            <th>Nội dung</th>
            <th>Kết quả</th>
            <th />
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in deliveries.data.value.items" :key="item.id">
            <td class="muted">{{ formatDate(item.created_at, true) }}</td>
            <td>{{ KIND[item.kind] }}</td>
            <td>
              <code>{{ item.event_type }}</code
              ><small v-if="item.subject" class="muted"> · {{ item.subject.type }} {{ item.subject.id.slice(0, 8) }}</small>
            </td>
            <td>
              <span :class="{ 'overdue-text': ['failed', 'unknown'].includes(item.state) }">{{
                DELIVERY[item.state as keyof typeof DELIVERY] ?? item.state
              }}</span
              ><small v-if="item.status_code" class="muted"> · {{ item.status_code }}</small
              ><small v-if="item.attempts > 1" class="muted"> · {{ item.attempts }} lần</small>
              <small v-if="item.error" class="muted plugin-log-error">{{ item.error }}</small>
            </td>
            <td>
              <button
                v-if="item.kind === 'event' && ['failed', 'unknown', 'cancelled'].includes(item.state)"
                class="button ghost small"
                :disabled="!!retrying"
                @click="retry(item)"
              >
                <RefreshCw :size="14" :class="{ spin: retrying === item.id }" />{{ retrying === item.id ? 'Đang gửi…' : 'Gửi lại' }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </ModalDialog>
</template>
<style scoped>
/* ---- Install: steps, drop zone, preview ---- */
.install-steps {
  display: flex;
  gap: 8px;
  margin: 0 0 20px;
  padding: 0;
  list-style: none;
  counter-reset: step;
}
.install-steps li {
  display: flex;
  flex: 1;
  gap: 8px;
  align-items: center;
  min-width: 0;
  color: var(--muted);
  font-size: 13.5px;
  font-weight: 600;
  white-space: nowrap;
}
.install-steps li:not(:last-child)::after {
  content: '';
  flex: 1;
  height: 2px;
  min-width: 12px;
  border-radius: 2px;
  background: var(--border);
}
.install-steps li > span {
  display: grid;
  place-items: center;
  flex: none;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  border: 1.5px solid var(--border-strong);
  font-size: 12px;
}
.install-steps li.current {
  color: var(--teal-ink);
}
.install-steps li.current > span {
  border-color: var(--teal);
  color: #fff;
  background: var(--teal);
}
.install-steps li.done {
  color: var(--green-ink);
}
.install-steps li.done > span {
  border-color: var(--green-ink);
  color: var(--green-ink);
  background: var(--green-soft);
}
.install-steps li.done::after {
  background: var(--green-line);
}
.install-drop {
  display: grid;
  gap: 6px;
  justify-items: center;
  padding: 34px 20px;
  border: 2px dashed var(--border-strong);
  border-radius: 14px;
  background: var(--surface-2);
  text-align: center;
  cursor: pointer;
  transition:
    border-color 0.15s,
    background 0.15s;
}
.install-drop:hover,
.install-drop.dragging {
  border-color: var(--teal);
  background: var(--teal-soft);
}
.install-drop:focus-within {
  outline: 2px solid var(--focus);
  outline-offset: 2px;
}
.install-drop strong {
  font-size: 16px;
}
.install-drop-icon {
  display: grid;
  place-items: center;
  width: 52px;
  height: 52px;
  margin-bottom: 4px;
  border-radius: 14px;
  color: var(--teal-ink);
  background: var(--surface);
  box-shadow: var(--shadow-sm);
}
.install-drop-link {
  color: var(--teal-ink);
  font-weight: 600;
  text-decoration: underline;
  text-underline-offset: 2px;
}
.install-kinds {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 12px;
  margin-top: 16px;
}
.install-kind {
  display: flex;
  gap: 12px;
  padding: 14px;
  border: 1px solid var(--border);
  border-radius: 12px;
}
.install-kind p {
  margin: 4px 0 0;
  font-size: 13.5px;
  line-height: 1.5;
}
.install-kind-icon,
.install-head-icon {
  display: grid;
  place-items: center;
  flex: none;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  color: var(--teal-ink);
  background: var(--teal-soft);
}
.install-note {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  margin: 16px 0 0;
  font-size: 13.5px;
}
.install-note svg {
  flex: none;
  margin-top: 2px;
}
.install-loading {
  display: flex;
  gap: 10px;
  align-items: center;
  justify-content: center;
  padding: 40px 0;
  color: var(--muted);
}
.install-preview {
  display: grid;
  gap: 14px;
}
.install-head {
  display: flex;
  gap: 14px;
  align-items: flex-start;
}
.install-head-icon {
  width: 52px;
  height: 52px;
  border-radius: 14px;
}
.install-head-text {
  display: grid;
  gap: 6px;
  min-width: 0;
}
.install-head h3 {
  margin: 0;
  font-size: 19px;
  line-height: 1.3;
}
.install-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.install-badges .tag {
  display: inline-flex;
  gap: 4px;
  align-items: center;
}
.tag.kind-packaged {
  color: var(--violet-ink);
  background: var(--violet-soft);
}
.tag.kind-connected {
  color: var(--blue-ink);
  background: var(--blue-soft);
}
.install-desc {
  margin: 0;
  line-height: 1.6;
}
.install-source {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  padding: 10px 12px;
  border-radius: 10px;
  color: var(--ink-2);
  background: var(--surface-2);
  font-size: 13.5px;
}
.install-source code {
  overflow-wrap: anywhere;
}
.install-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 12px;
}
.install-section {
  display: grid;
  align-content: start;
  gap: 8px;
  padding: 14px 16px;
  border: 1px solid var(--border);
  border-radius: 12px;
}
.install-section h4,
.approve-group h4 {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin: 0;
  font-size: 14.5px;
}
.install-section h4 svg,
.approve-group h4 svg {
  color: var(--teal-ink);
}
.install-section p {
  margin: 0;
}
.install-list {
  display: grid;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
  font-size: 14px;
  line-height: 1.45;
}
.install-list li {
  display: flex;
  gap: 8px;
  align-items: flex-start;
}
.install-li-icon {
  flex: none;
  margin-top: 2px;
  color: var(--muted);
}
.scope {
  flex: none;
  min-width: 38px;
  text-align: center;
  padding: 1px 7px;
  border-radius: 6px;
  font-size: 11.5px;
  font-weight: 700;
  letter-spacing: 0.02em;
  text-transform: uppercase;
}
.scope.read {
  color: var(--green-ink);
  background: var(--green-soft);
}
.scope.write {
  color: var(--amber-ink);
  background: var(--amber-soft);
}
.install-fields,
.install-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}
.install-fields code {
  padding: 2px 7px;
  border-radius: 6px;
  background: var(--surface-2);
  font-size: 12.5px;
}
.install-actions .grow {
  flex: 1;
}
/* ---- Approval ---- */
.approve-summary {
  display: flex;
  gap: 16px;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 14px;
}
.approve-summary p {
  margin: 0;
}
.approve-count {
  flex: none;
  padding: 4px 10px;
  border-radius: 999px;
  color: var(--teal-ink);
  background: var(--teal-soft);
  font-size: 13px;
  font-weight: 700;
}
.approve-groups {
  display: grid;
  gap: 12px;
}
.approve-group {
  display: grid;
  gap: 4px;
  padding: 12px 14px;
  border: 1px solid var(--border);
  border-radius: 12px;
}
.approve-group > header {
  display: flex;
  gap: 8px;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}
.approve-item {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  padding: 8px 6px;
  border-radius: 8px;
  cursor: pointer;
}
.approve-item:hover {
  background: var(--surface-2);
}
.approve-item input {
  flex: none;
  margin-top: 3px;
}
.approve-text {
  display: grid;
  flex: 1;
  gap: 2px;
  font-size: 14px;
  line-height: 1.4;
}
.approve-text code {
  width: fit-content;
  color: var(--muted);
  font-size: 12px;
}
.approve-hint {
  display: flex;
  gap: 6px;
  align-items: flex-start;
  margin: 4px 0 0;
  padding: 8px 10px;
  border-radius: 8px;
  color: var(--amber-ink);
  background: var(--amber-soft);
  font-size: 13px;
}
.approve-hint svg {
  flex: none;
  margin-top: 2px;
}
.approve-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.approve-chip {
  display: inline-flex;
  gap: 4px;
  align-items: center;
  padding: 4px 10px;
  border: 1px solid var(--border-strong);
  border-radius: 999px;
  cursor: pointer;
  font-size: 13px;
}
.approve-chip.on {
  border-color: var(--teal);
  color: var(--teal-ink);
  background: var(--teal-soft);
}
.approve-chip:focus-within {
  outline: 2px solid var(--focus);
  outline-offset: 2px;
}
@media (max-width: 560px) {
  .install-steps li {
    font-size: 0;
  }
  .install-steps li.current {
    flex: 1 0 auto;
    font-size: 13px;
  }
  .approve-summary {
    flex-direction: column;
    gap: 8px;
  }
  .install-actions {
    flex-wrap: wrap;
  }
  .install-actions .grow {
    display: none;
  }
}
.plugin-hosts {
  margin: 0 0 16px;
}
.plugin-footnote {
  margin-top: 16px;
  font-size: 0.8438rem;
  line-height: 1.55;
}
.plugin-log-error {
  display: block;
  margin-top: 4px;
}
.plugin-row {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  align-items: flex-start;
  padding: 20px;
  border-top: 1px solid var(--border-soft);
}
.plugin-row:first-child {
  border-top: 0;
}
.plugin-row .grow {
  display: grid;
  gap: 6px;
  flex: 1;
  min-width: 240px;
}
.plugin-row p {
  margin: 2px 0;
}
.plugin-icon {
  display: grid;
  place-items: center;
  flex: none;
  width: 44px;
  height: 44px;
  border-radius: 12px;
  color: var(--muted);
  background: var(--surface-2);
}
.plugin-icon.enabled {
  color: var(--teal-ink);
  background: var(--teal-soft);
}
.plugin-title {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.tag.state-enabled {
  color: var(--green-ink);
  background: var(--green-soft);
}
.tag.state-pending {
  color: var(--amber-ink);
  background: var(--amber-soft);
}
.tag.state-bad {
  color: var(--red-ink);
  background: var(--red-soft);
}
.plugin-facts {
  display: grid;
  gap: 8px;
  margin: 6px 0 0;
  padding: 0;
  list-style: none;
  font-size: 0.8438rem;
}
.plugin-facts strong {
  margin-right: 6px;
}
.plugin-facts .chip {
  margin: 0 6px 4px 0;
}
.plugin-facts .chip.off {
  text-decoration: line-through;
  opacity: 0.6;
}
.plugin-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.plugin-remove:hover:not(:disabled) {
  color: var(--red-ink);
}
@media (max-width: 640px) {
  .plugin-row {
    padding: 16px;
  }
  .plugin-row .grow {
    min-width: 0;
    flex-basis: calc(100% - 60px);
  }
  .plugin-row small.mono {
    overflow-wrap: anywhere;
  }
  .plugin-actions {
    width: 100%;
  }
}
.plugin-secret {
  display: flex;
  gap: 8px;
  align-items: center;
}
.plugin-secret code {
  flex: 1;
  overflow-wrap: anywhere;
  padding: 8px 10px;
  border-radius: 8px;
  background: var(--surface-2);
}
</style>
