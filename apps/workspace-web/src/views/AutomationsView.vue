<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { ArrowRight, CirclePause, FileCheck2, Paperclip, Plug, Plus, Workflow, Zap } from 'lucide-vue-next'
import { api } from '../api'
import { errorText, formatDate } from '@dx/web-shared/api.ts'
import type { Page } from '@dx/web-shared/api.ts'
import StatePanel from '@dx/web-shared/components/StatePanel.vue'
import StatusBadge from '@dx/web-shared/components/StatusBadge.vue'
import ModalDialog from '@dx/web-shared/components/ModalDialog.vue'
import { KINDS, TEMPLATES } from '../flow/nodes'
import { usePackTemplates } from '../flow/templates'
import ProcessFormDialog from '../flow/ProcessFormDialog.vue'
import '../flow/flow.css'
import type { ApiGraph, FlowKind } from '../flow/nodes'
interface Rule {
  id: string
  kind: FlowKind
  form_id: string | null
  form_name: string | null
  name: string
  description: string
  trigger: string
  enabled: boolean
  revision: number
  graph: ApiGraph
  scope: 'all' | 'attached'
  attached_count: number
  active_version_no: number | null
  unpublished_changes: boolean
  updated_at: string
  last_run: { state: string; created_at: string } | null
}
interface Connection {
  id: string
  name: string
  base_url: string
  auth_type: string
  timeout_seconds: number
}
const router = useRouter()
const queryClient = useQueryClient()
const catalog = useQuery({
  queryKey: ['automations', 'catalog'],
  queryFn: () =>
    api.request<{
      triggers: { key: string; label: string }[]
      webhooks_enabled: boolean
      allowed_hosts: string[]
      process: { forms: { id: string; name: string }[] }
    }>('/automations/catalog'),
})
const packTemplates = usePackTemplates()
const forms = computed(() => catalog.data.value?.process.forms ?? [])
const rules = useQuery({
  queryKey: ['automations'],
  queryFn: () => api.request<Page<Rule>>('/automations'),
})
const connections = useQuery({
  queryKey: ['connections'],
  queryFn: () => api.request<Page<Connection>>('/connections'),
})
const shown = computed(() => rules.data.value?.items ?? [])
/** Form a new process is drawn for; templates open with it already chosen. */
const templateForm = ref('')
function openProcess(query: Record<string, string>) {
  void router.push({
    path: '/processes/new',
    query: { ...(query.template?.startsWith('process') || query.from_form ? (templateForm.value ? { form: templateForm.value } : {}) : {}), ...query },
  })
}
const triggerLabel = computed(() =>
  Object.fromEntries((catalog.data.value?.triggers ?? []).map((t) => [t.key, t.label])),
)
const error = ref<unknown>(null)
const busy = ref(false)
const showTemplates = ref(false)
const creatingForm = ref(false)
async function formCreated(formId: string) {
  creatingForm.value = false
  await catalog.refetch()
  templateForm.value = formId
}
/** A tiny left-to-right sketch of the flow for the list card. */
function sketch(graph: ApiGraph) {
  const xs = graph.nodes.map((n) => n.position.x)
  const ys = graph.nodes.map((n) => n.position.y)
  const minX = Math.min(...xs)
  const minY = Math.min(...ys)
  const spanX = Math.max(1, Math.max(...xs) - minX)
  const spanY = Math.max(1, Math.max(...ys) - minY)
  const place = (id: string) => {
    const node = graph.nodes.find((n) => n.id === id)!
    return {
      x: 14 + ((node.position.x - minX) / spanX) * 172,
      y: 14 + ((node.position.y - minY) / spanY) * 42,
    }
  }
  return {
    nodes: graph.nodes.map((n) => ({ ...place(n.id), color: KINDS[n.type]?.color ?? '#999', id: n.id })),
    edges: graph.edges
      .filter((e) => graph.nodes.some((n) => n.id === e.source) && graph.nodes.some((n) => n.id === e.target))
      .map((e) => ({ from: place(e.source), to: place(e.target), id: e.id })),
  }
}
const connectionForm = ref<{
  name: string
  base_url: string
  auth_type: string
  secret: string
  secret_header: string
  timeout_seconds: number
} | null>(null)
async function saveConnection() {
  const value = connectionForm.value
  if (!value) return
  busy.value = true
  error.value = null
  try {
    await api.request('/connections', {
      method: 'POST',
      body: JSON.stringify({ ...value, secret: value.secret || null }),
    })
    connectionForm.value = null
    await queryClient.invalidateQueries({ queryKey: ['connections'] })
  } catch (cause) {
    error.value = cause
  } finally {
    busy.value = false
  }
}
</script>
<template>
  <header class="page-head compact">
    <h1 class="sr-only">Quy trình nghiệp vụ</h1>
    <div class="page-actions">
      <button class="button" @click="showTemplates = true"><Plus :size="18" />Tạo luồng</button>
    </div>
  </header>
  <div v-if="error && !connectionForm" class="notice error error-inline">{{ errorText(error) }}</div>
  <section v-if="rules.isPending.value || rules.error.value || !shown.length" class="card">
    <StatePanel
      :loading="rules.isPending.value"
      :error="rules.error.value"
      :empty="!rules.isPending.value && !shown.length"
      title="Chưa có luồng nào"
      description="Bắt đầu từ một mẫu có sẵn, chỉnh trên canvas rồi phát hành."
      @retry="rules.refetch()"
      ><button class="button small" @click="showTemplates = true">
        <Plus :size="16" />Tạo luồng
      </button></StatePanel
    >
  </section>
  <div class="flow-cards">
    <article v-for="rule in shown" :key="rule.id" class="card flow-card">
      <RouterLink :to="`/processes/${rule.id}`" class="flow-card-sketch" :aria-label="`Mở ${rule.name}`">
        <svg viewBox="0 0 200 70" aria-hidden="true">
          <path
            v-for="edge in sketch(rule.graph).edges"
            :key="edge.id"
            :d="`M${edge.from.x},${edge.from.y} C${(edge.from.x + edge.to.x) / 2},${edge.from.y} ${(edge.from.x + edge.to.x) / 2},${edge.to.y} ${edge.to.x},${edge.to.y}`"
            fill="none"
            stroke="#b8c7d3"
            stroke-width="1.6"
          />
          <rect
            v-for="node in sketch(rule.graph).nodes"
            :key="node.id"
            :x="node.x - 9"
            :y="node.y - 7"
            width="18"
            height="14"
            rx="4"
            :fill="node.color"
          />
        </svg>
      </RouterLink>
      <div class="flow-card-body">
        <div class="flow-card-title">
          <RouterLink :to="`/processes/${rule.id}`" class="row-link">{{ rule.name }}</RouterLink>
          <span class="tag">{{
            rule.active_version_no ? `Phiên bản ${rule.active_version_no}` : 'Bản nháp'
          }}</span>
        </div>
        <small class="flow-card-when" :class="rule.enabled ? 'on' : 'off'">
          <template v-if="rule.kind === 'process' && rule.enabled"
            ><FileCheck2 :size="14" aria-hidden="true" class="inline-icon" /> Đang áp dụng cho biểu mẫu <strong>“{{ rule.form_name ?? 'biểu mẫu' }}”</strong
            ><template v-if="rule.unpublished_changes"> · có thay đổi chưa phát hành</template></template
          >
          <template v-else-if="rule.kind === 'process'"
            ><CirclePause :size="14" aria-hidden="true" class="inline-icon" /> Chưa phát hành, chưa ai dùng được<template v-if="rule.form_name">
              · biểu mẫu <strong>“{{ rule.form_name }}”</strong></template
            ></template
          >
          <template v-else-if="rule.enabled && rule.scope === 'attached'"
            ><Paperclip :size="14" aria-hidden="true" class="inline-icon" /> Chạy cho {{ rule.attached_count }} công việc được gắn, mỗi khi
            <strong>{{ triggerLabel[rule.trigger] ?? rule.trigger }}</strong></template
          >
          <template v-else-if="rule.enabled"
            ><Zap :size="14" aria-hidden="true" class="inline-icon" /> Tự chạy mỗi khi <strong>{{ triggerLabel[rule.trigger] ?? rule.trigger }}</strong></template
          >
          <template v-else
            ><CirclePause :size="14" aria-hidden="true" class="inline-icon" /> Chưa phát hành — sẽ không tự chạy khi
            <strong>{{ triggerLabel[rule.trigger] ?? rule.trigger }}</strong></template
          >
          · {{ rule.graph.nodes.length }} bước
        </small>
        <div class="flow-card-foot">
          <StatusBadge v-if="rule.last_run" :status="rule.last_run.state" />
          <small v-if="rule.last_run" class="muted">{{ formatDate(rule.last_run.created_at, true) }}</small>
          <small v-else class="muted">Chưa chạy lần nào</small>
          <RouterLink :to="`/processes/${rule.id}`" class="button ghost small" style="margin-left: auto"
            >Mở canvas <ArrowRight :size="14"
          /></RouterLink>
        </div>
      </div>
    </article>
  </div>

  <section class="card" style="margin-top: 22px">
    <header class="card-header">
      <div><span class="eyebrow">KẾT NỐI NGOÀI</span><h2>Kết nối webhook</h2></div>
      <button
        class="button secondary small"
        :disabled="!catalog.data.value?.webhooks_enabled"
        @click="
          connectionForm = {
            name: '',
            base_url: 'https://',
            auth_type: 'none',
            secret: '',
            secret_header: 'X-API-Key',
            timeout_seconds: 10,
          }
        "
      >
        <Plug :size="15" />Thêm kết nối
      </button>
    </header>
    <p v-if="catalog.data.value && !catalog.data.value.webhooks_enabled" class="card-body muted">
      Hệ thống chưa cho phép gửi dữ liệu sang hệ thống khác. Liên hệ bộ phận kỹ thuật để mở danh sách máy chủ được
      phép kết nối.
    </p>
    <p v-else-if="catalog.data.value" class="card-body muted" style="padding-bottom: 0">
      Máy chủ được phép: <code>{{ catalog.data.value.allowed_hosts.join(', ') }}</code>. Khóa bí mật được mã hóa và
      không bao giờ hiển thị lại.
    </p>
    <div v-for="item in connections.data.value?.items" :key="item.id" class="list-row">
      <div class="grow">
        <p>{{ item.name }}</p>
        <small class="mono">{{ item.base_url }}</small>
      </div>
      <span class="tag">{{ item.auth_type === 'none' ? 'Không xác thực' : 'Có khóa bí mật' }}</span>
      <span class="tag">{{ item.timeout_seconds }}s</span>
    </div>
  </section>

  <ModalDialog
    v-if="showTemplates"
    title="Tạo luồng"
    wide
    @close="showTemplates = false"
  >
    <div class="field" style="margin-bottom: 14px">
      <label for="template-form">Biểu mẫu áp dụng</label
      ><select id="template-form" v-model="templateForm">
        <option value="">Chọn sau trên canvas…</option>
        <option v-for="form in forms" :key="form.id" :value="form.id">{{ form.name }}</option>
      </select>
      <small class="muted"
        >Biểu mẫu là những gì người tạo hồ sơ phải điền.
        <button type="button" class="button ghost small" @click="creatingForm = true">Tạo biểu mẫu mới</button></small
      >
    </div>
    <div class="template-grid">
      <button
        class="template-card"
        :disabled="!templateForm"
        :title="templateForm ? '' : 'Chọn biểu mẫu trước'"
        @click="openProcess({ from_form: templateForm })"
      >
        <span class="template-dots"><i style="background: #e8833a" /><i style="background: #1f8a5b" /></span>
        <strong>Từ bước duyệt của biểu mẫu</strong>
        <small>Vẽ lại đúng các bước duyệt đang khai trong biểu mẫu (kể cả điều kiện) để chỉnh tiếp trên canvas.</small>
      </button>
      <button
        v-for="template in packTemplates.data.value ?? []"
        :key="`${template.pack_id}:${template.key}`"
        class="template-card"
        @click="openProcess({ template: template.key })"
      >
        <span class="template-dots">
          <i
            v-for="node in template.graph.nodes"
            :key="node.id"
            :style="{ background: KINDS[node.type]?.color ?? '#8fa3b5' }"
          />
        </span>
        <strong>{{ template.title }}</strong>
        <span v-if="template.pack_id !== 'desktiny.core'" class="tag">{{ template.pack_name }}</span>
        <small>{{ template.description }}</small>
      </button>
    </div>
    <span class="section-label" style="display: block; margin: 18px 0 10px">Phản ứng với sự kiện</span>
    <div class="template-grid">
      <button
        v-for="template in TEMPLATES"
        :key="template.key"
        class="template-card"
        @click="openProcess({ template: template.key })"
      >
        <span class="template-dots">
          <i
            v-for="node in template.graph.nodes"
            :key="node.id"
            :style="{ background: KINDS[node.type].color }"
          />
        </span>
        <strong>{{ template.title }}</strong>
        <small>{{ template.description }}</small>
      </button>
    </div>
  </ModalDialog>
  <ProcessFormDialog v-if="creatingForm" @close="creatingForm = false" @created="formCreated" />
  <ModalDialog v-if="connectionForm" title="Thêm kết nối webhook" @close="connectionForm = null">
    <div v-if="error" class="notice error error-inline">{{ errorText(error) }}</div>
    <form class="stack" @submit.prevent="saveConnection">
      <div class="field">
        <label for="conn-name">Tên</label><input id="conn-name" v-model="connectionForm.name" required />
      </div>
      <div class="field">
        <label for="conn-url">Địa chỉ gốc</label><input id="conn-url" v-model="connectionForm.base_url" type="url" required />
      </div>
      <div class="form-grid">
        <div class="field">
          <label for="conn-auth">Xác thực</label
          ><select id="conn-auth" v-model="connectionForm.auth_type">
            <option value="none">Không</option>
            <option value="bearer">Bearer token</option>
            <option value="header">Header khóa API</option>
          </select>
        </div>
        <div class="field">
          <label for="conn-timeout">Thời gian chờ (giây)</label
          ><input id="conn-timeout" v-model.number="connectionForm.timeout_seconds" type="number" min="1" max="60" />
        </div>
      </div>
      <div v-if="connectionForm.auth_type === 'header'" class="field">
        <label for="conn-header">Tên header</label
        ><input id="conn-header" v-model="connectionForm.secret_header" required placeholder="X-API-Key" />
      </div>
      <div v-if="connectionForm.auth_type !== 'none'" class="field">
        <label for="conn-secret">Khóa bí mật</label
        ><input id="conn-secret" v-model="connectionForm.secret" type="password" autocomplete="off" required />
      </div>
      <div class="form-actions">
        <button type="button" class="button secondary" @click="connectionForm = null">Hủy</button
        ><button class="button" :disabled="busy">Lưu kết nối</button>
      </div>
    </form>
  </ModalDialog>
  <p class="muted" style="margin-top: 18px; font-size: 14px">
    <Workflow :size="14" style="vertical-align: -2px" /> Mỗi sự kiện chỉ chạy mỗi luồng một lần. Luồng không tự chạy
    lại vì chính việc nó làm, và các luồng nối tiếp nhau sẽ dừng sau vài bước để tránh chạy vòng mãi.
  </p>
</template>
