<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<!-- Connected plugins: install from a manifest, approve what each asks for, switch on and off, rotate
     keys, read what was exchanged. Secrets and tokens are shown once, when issued. -->
<script setup lang="ts">
import { computed, ref } from 'vue'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import {
  AlertTriangle,
  Copy,
  KeyRound,
  ListChecks,
  Power,
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
  permissions: Labelled[]
  events: Labelled[]
  nodes: { kind: string; title: string; description: string }[]
  ui: { slot: string; slot_label: string; title: string }[]
  host_allowed: boolean
}
interface PluginRow extends PluginSummary {
  state: 'pending' | 'enabled' | 'disabled'
  granted: { permissions: string[]; events: string[] }
  revision: number
  approved_at: string | null
  updated_at: string
  last_day: Record<string, number>
}
interface Delivery {
  id: string
  kind: 'event' | 'node' | 'api'
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
const preview = ref<(PluginSummary & { upgrade_from: string | null }) | null>(null)
const previewFile = ref<File | null>(null)
const previewError = ref<unknown>(null)
const approving = ref<PluginRow | null>(null)
const chosen = ref<{ permissions: string[]; events: string[] }>({ permissions: [], events: [] })
const issued = ref<{ name: string; values: Issued } | null>(null)
const removing = ref<PluginRow | null>(null)
const logOf = ref<PluginRow | null>(null)

const STATE = { pending: 'Chờ duyệt', enabled: 'Đang bật', disabled: 'Đang tắt' }
const KIND = { event: 'Sự kiện', node: 'Bước quy trình', api: 'Đọc API' }
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
async function pick(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
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
  if (!previewFile.value) return
  busy.value = true
  try {
    const row = await api.request<PluginRow>('/plugins', { method: 'POST', body: form(previewFile.value) })
    toast.success(row.state === 'pending' ? 'Đã cài. Duyệt quyền để bật plugin.' : 'Đã nâng cấp plugin.')
    previewFile.value = null
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
  }
}
function toggleIn(list: string[], key: string) {
  const index = list.indexOf(key)
  if (index >= 0) list.splice(index, 1)
  else list.push(key)
}
async function approve() {
  if (!approving.value) return
  busy.value = true
  try {
    const result = await api.request<PluginRow & { issued: Issued }>(
      `/plugins/${encodeURIComponent(approving.value.id)}/approve`,
      { method: 'POST', body: JSON.stringify({ expected_revision: approving.value.revision, ...chosen.value }) },
    )
    issued.value = { name: result.name, values: result.issued }
    approving.value = null
    await refresh()
  } catch (cause) {
    toast.error(cause)
  } finally {
    busy.value = false
  }
}
async function act(row: PluginRow, path: 'enabled' | 'rotate', body: Record<string, unknown> = {}) {
  busy.value = true
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
  }
}
async function remove() {
  if (!removing.value) return
  busy.value = true
  try {
    await api.request(`/plugins/${encodeURIComponent(removing.value.id)}`, { method: 'DELETE' })
    toast.success(`Đã gỡ “${removing.value.name}”.`)
    removing.value = null
    await refresh()
  } catch (cause) {
    toast.error(cause)
  } finally {
    busy.value = false
  }
}
async function retry(delivery: Delivery) {
  try {
    await api.request(`/plugins/${encodeURIComponent(logOf.value!.id)}/deliveries/${delivery.id}/retry`, {
      method: 'POST',
    })
    toast.success('Đã xếp hàng gửi lại.')
    await deliveries.refetch()
  } catch (cause) {
    toast.error(cause)
  }
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
      <label class="button"
        ><Upload :size="17" />Cài plugin (manifest)<input
          type="file"
          accept=".json,.zip,application/json,application/zip"
          class="sr-only"
          @change="pick"
      /></label>
    </div>
  </header>
  <StatePanel
    v-if="listing.isPending.value || listing.error.value"
    :loading="listing.isPending.value"
    :error="listing.error.value"
    @retry="listing.refetch()"
  />
  <template v-else-if="listing.data.value">
    <div v-if="!listing.data.value.allowed_hosts.length" class="notice warning" style="margin-bottom: 18px">
      <AlertTriangle :size="18" /><span
        >Triển khai chưa cho phép máy chủ plugin nào. Bộ phận kỹ thuật cần khai tên máy chủ của plugin trong
        <code>PLUGIN_ALLOWED_HOSTS</code> (và địa chỉ của nó trong <code>PLUGIN_FRAME_SOURCES</code> nếu plugin có khung
        giao diện).</span
      >
    </div>
    <p v-else class="muted" style="margin: 0 0 14px">
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
            <span v-if="!row.host_allowed" class="tag state-bad">Máy chủ chưa được phép</span>
          </div>
          <small class="muted mono">{{ row.id }} · {{ row.version }} · {{ row.base_url }}</small>
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
            <li v-if="row.nodes.length">
              <strong>Bước quy trình:</strong> {{ row.nodes.map((n) => n.title).join(', ') }}
            </li>
            <li v-if="row.ui.length">
              <strong>Khung giao diện:</strong> {{ row.ui.map((u) => `${u.title} (${u.slot_label})`).join(', ') }}
            </li>
            <li v-if="row.state !== 'pending'" class="muted">
              24 giờ qua: {{ row.last_day.sent ?? 0 }} lần thành công<template v-if="row.last_day.failed">
                · <span class="overdue-text">{{ row.last_day.failed }} bị từ chối</span></template
              ><template v-if="row.last_day.pending"> · {{ row.last_day.pending }} đang gửi</template>
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
            :disabled="busy"
            @click="act(row, 'enabled', { enabled: row.state !== 'enabled' })"
          >
            <Power :size="15" />{{ row.state === 'enabled' ? 'Tắt' : 'Bật' }}
          </button>
          <button v-if="row.state !== 'pending'" class="button ghost small" :disabled="busy" @click="openApprove(row)">
            <ShieldCheck :size="15" />Quyền
          </button>
          <button v-if="row.state !== 'pending'" class="button ghost small" :disabled="busy" @click="act(row, 'rotate')">
            <KeyRound :size="15" />Đổi khoá
          </button>
          <button class="button ghost small" @click="logOf = row"><ListChecks :size="15" />Nhật ký</button>
          <button class="button ghost small" @click="removing = row"><Trash2 :size="15" />Gỡ</button>
        </div>
      </article>
    </section>
    <p class="muted" style="margin-top: 16px; font-size: 13.5px">
      Mã của plugin không chạy trong Desktiny. Sự kiện và lời gọi bước quy trình được ký HMAC; plugin chỉ đọc được hồ
      sơ nó đã được báo, hoặc theo quyền của người đang xem khung. Cách viết plugin: <code>docs/plugins.md</code>.
    </p>
  </template>

  <ModalDialog v-if="previewFile" title="Cài plugin" wide @close="previewFile = null">
    <div v-if="previewError" class="notice error error-inline">{{ errorText(previewError) }}</div>
    <StatePanel v-else-if="!preview" :loading="true" />
    <div v-if="preview" class="stack">
      <div>
        <strong>{{ preview.name }}</strong>
        <small class="muted mono">
          · {{ preview.id }} · <template v-if="preview.upgrade_from">{{ preview.upgrade_from }} → </template
          >{{ preview.version }} · {{ preview.license }}</small
        >
        <p v-if="preview.description">{{ preview.description }}</p>
        <small class="mono">{{ preview.base_url }}</small>
      </div>
      <div v-if="!preview.host_allowed" class="notice error">
        <AlertTriangle :size="18" /><span
          >Máy chủ của plugin chưa có trong <code>PLUGIN_ALLOWED_HOSTS</code>; không cài được.</span
        >
      </div>
      <div class="plugin-asks">
        <div>
          <span class="section-label">Xin quyền</span>
          <p v-if="!preview.permissions.length" class="muted">Không xin đọc dữ liệu.</p>
          <ul>
            <li v-for="item in preview.permissions" :key="item.key">{{ item.label }}</li>
          </ul>
        </div>
        <div>
          <span class="section-label">Nhận sự kiện</span>
          <p v-if="!preview.events.length" class="muted">Không nhận sự kiện.</p>
          <ul>
            <li v-for="item in preview.events" :key="item.key">{{ item.label }}</li>
          </ul>
        </div>
        <div>
          <span class="section-label">Thêm vào phần mềm</span>
          <ul>
            <li v-for="node in preview.nodes" :key="node.kind">Bước quy trình: {{ node.title }}</li>
            <li v-for="ui in preview.ui" :key="ui.title">Khung “{{ ui.title }}” ở {{ ui.slot_label.toLowerCase() }}</li>
          </ul>
        </div>
      </div>
      <small class="muted">Plugin được cài ở trạng thái chờ duyệt; nó chưa nhận gì cho tới khi bạn duyệt quyền.</small>
      <div class="form-actions">
        <button type="button" class="button secondary" @click="previewFile = null">Huỷ</button
        ><button type="button" class="button" :disabled="busy || !preview.host_allowed" @click="install">
          {{ preview.upgrade_from ? 'Nâng cấp' : 'Cài plugin' }}
        </button>
      </div>
    </div>
  </ModalDialog>

  <ModalDialog v-if="approving" :title="`Duyệt quyền: ${approving.name}`" @close="approving = null">
    <div class="stack">
      <p class="muted">Chỉ cấp những gì plugin thật sự cần. Bỏ chọn mục nào thì plugin không có mục đó.</p>
      <div v-if="approving.permissions.length">
        <span class="section-label">Quyền đọc</span>
        <label v-for="item in approving.permissions" :key="item.key" class="checkbox-label"
          ><input
            type="checkbox"
            :checked="chosen.permissions.includes(item.key)"
            @change="toggleIn(chosen.permissions, item.key)"
          />{{ item.label }}</label
        >
      </div>
      <div v-if="approving.events.length">
        <span class="section-label">Sự kiện được gửi</span>
        <label v-for="item in approving.events" :key="item.key" class="checkbox-label"
          ><input
            type="checkbox"
            :checked="chosen.events.includes(item.key)"
            @change="toggleIn(chosen.events, item.key)"
          />{{ item.label }}</label
        >
      </div>
      <div class="form-actions">
        <button type="button" class="button secondary" @click="approving = null">Huỷ</button
        ><button type="button" class="button" :disabled="busy" @click="approve">
          <ShieldCheck :size="16" />Duyệt và bật
        </button>
      </div>
    </div>
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
          ><button class="icon-button" type="button" aria-label="Sao chép khoá ký" @click="copy(issued.values.secret!)">
            <Copy :size="15" />
          </button>
        </div>
      </div>
      <div class="field">
        <label>Token gọi API plugin</label>
        <div class="plugin-secret">
          <code>{{ issued.values.token }}</code
          ><button class="icon-button" type="button" aria-label="Sao chép token" @click="copy(issued.values.token)">
            <Copy :size="15" />
          </button>
        </div>
      </div>
      <div class="form-actions">
        <button type="button" class="button" @click="issued = null">Đã lưu</button>
      </div>
    </div>
  </ModalDialog>

  <ModalDialog v-if="removing" title="Gỡ plugin" @close="removing = null">
    <div class="stack">
      <p>
        Gỡ <strong>{{ removing.name }}</strong>? Mọi token của plugin hết hiệu lực ngay; khung giao diện biến mất; bước
        quy trình của plugin sẽ báo lỗi và dừng có lý do cho tới khi được thay.
      </p>
      <div class="form-actions">
        <button type="button" class="button secondary" @click="removing = null">Huỷ</button
        ><button type="button" class="button danger" :disabled="busy" @click="remove">Gỡ plugin</button>
      </div>
    </div>
  </ModalDialog>

  <ModalDialog v-if="logOf" :title="`Nhật ký: ${logOf.name}`" wide @close="logOf = null">
    <StatePanel
      v-if="deliveries.isPending.value || !deliveries.data.value?.items.length"
      :loading="deliveries.isPending.value"
      :empty="true"
      title="Chưa có trao đổi nào"
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
              <small v-if="item.error" class="muted" style="display: block">{{ item.error }}</small>
            </td>
            <td>
              <button
                v-if="item.kind === 'event' && ['failed', 'unknown', 'cancelled'].includes(item.state)"
                class="button ghost small"
                @click="retry(item)"
              >
                <RefreshCw :size="14" />Gửi lại
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </ModalDialog>
</template>
<style scoped>
.plugin-row {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  align-items: flex-start;
  padding: 16px 18px;
  border-top: 1px solid var(--border-soft);
}
.plugin-row:first-child {
  border-top: 0;
}
.plugin-row .grow {
  display: grid;
  gap: 4px;
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
  gap: 4px;
  margin: 4px 0 0;
  padding: 0;
  list-style: none;
  font-size: 13.5px;
}
.plugin-facts .chip {
  margin: 0 4px 2px 0;
}
.plugin-facts .chip.off {
  text-decoration: line-through;
  opacity: 0.6;
}
.plugin-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.plugin-asks {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 14px;
}
.plugin-asks ul {
  margin: 4px 0 0;
  padding-left: 18px;
}
.plugin-secret {
  display: flex;
  gap: 6px;
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
