<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { ArrowRight, Plug, Plus, Workflow } from 'lucide-vue-next'
import { api } from '../api'
import { toast } from '../ui/toast'
import { errorText, formatDate } from '@dx/web-shared/api.ts'
import type { Page } from '@dx/web-shared/api.ts'
import StatePanel from '@dx/web-shared/components/StatePanel.vue'
import StatusBadge from '@dx/web-shared/components/StatusBadge.vue'
import ModalDialog from '@dx/web-shared/components/ModalDialog.vue'
import { KINDS, TEMPLATES } from '../flow/nodes'
import '../flow/flow.css'
import type { ApiGraph } from '../flow/nodes'
interface Rule {
  id: string
  name: string
  description: string
  trigger: string
  enabled: boolean
  revision: number
  graph: ApiGraph
  scope: 'all' | 'attached'
  attached_count: number
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
    }>('/automations/catalog'),
})
const rules = useQuery({
  queryKey: ['automations'],
  queryFn: () => api.request<Page<Rule>>('/automations'),
})
const connections = useQuery({
  queryKey: ['connections'],
  queryFn: () => api.request<Page<Connection>>('/connections'),
})
const triggerLabel = computed(() =>
  Object.fromEntries((catalog.data.value?.triggers ?? []).map((t) => [t.key, t.label])),
)
const error = ref<unknown>(null)
const busy = ref(false)
const showTemplates = ref(false)
async function toggle(rule: Rule) {
  busy.value = true
  error.value = null
  try {
    await api.request(`/automations/${rule.id}/enabled`, {
      method: 'POST',
      body: JSON.stringify({ expected_revision: rule.revision, enabled: !rule.enabled }),
    })
    toast.success(rule.enabled ? `Đã tắt “${rule.name}”` : `Đã bật “${rule.name}”`)
    await queryClient.invalidateQueries({ queryKey: ['automations'] })
  } catch (cause) {
    error.value = cause
  } finally {
    busy.value = false
  }
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
  <header class="page-head">
    <div>
      <span class="eyebrow">TỰ ĐỘNG HÓA NGHIỆP VỤ</span>
      <h1>Luồng tự động</h1>
      <p>Vẽ luồng bằng kéo thả: khi sự kiện xảy ra → kiểm tra điều kiện → thông báo, tạo việc, chờ hoặc gọi hệ thống khác.</p>
    </div>
    <div class="page-actions">
      <button class="button" @click="showTemplates = true"><Plus :size="18" />Tạo luồng</button>
    </div>
  </header>
  <section class="how-it-works" aria-label="Cách luồng tự động hoạt động">
    <div>
      <span class="how-step">1</span>
      <div>
        <strong>Chọn khi nào chạy</strong>
        <small
          >Mỗi luồng gắn với một sự kiện có sẵn: công việc được nộp kết quả, bị trả lại; hồ sơ được trình, được
          duyệt; bài viết mới…</small
        >
      </div>
    </div>
    <div>
      <span class="how-step">2</span>
      <div>
        <strong>Bật luồng — không cần bấm chạy</strong>
        <small
          >Luồng đang bật <b>tự chạy</b> mỗi khi sự kiện đó xảy ra ở bất kỳ công việc/hồ sơ nào. Luồng tắt thì không
          chạy.</small
        >
      </div>
    </div>
    <div>
      <span class="how-step">3</span>
      <div>
        <strong>Kiểm tra và theo dõi</strong>
        <small
          ><b>Chạy thử</b> xem đường đi mà không tác động thật; <b>Chạy ngay</b> áp dụng cho một bản ghi có sẵn;
          <b>Lịch sử chạy</b> cho biết đã chạy cho việc nào.</small
        >
      </div>
    </div>
  </section>
  <div v-if="error && !connectionForm" class="notice error error-inline">{{ errorText(error) }}</div>
  <section v-if="rules.isPending.value || rules.error.value || !rules.data.value?.items.length" class="card">
    <StatePanel
      :loading="rules.isPending.value"
      :error="rules.error.value"
      :empty="rules.data.value?.items.length === 0"
      title="Chưa có luồng tự động"
      description="Bắt đầu từ một mẫu có sẵn, chỉnh trên canvas và chạy thử trước khi bật."
      @retry="rules.refetch()"
      ><button class="button small" @click="showTemplates = true"><Plus :size="16" />Tạo luồng</button></StatePanel
    >
  </section>
  <div class="flow-cards">
    <article v-for="rule in rules.data.value?.items" :key="rule.id" class="card flow-card">
      <RouterLink :to="`/automations/${rule.id}`" class="flow-card-sketch" :aria-label="`Mở ${rule.name}`">
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
          <RouterLink :to="`/automations/${rule.id}`" class="row-link">{{ rule.name }}</RouterLink>
          <label class="switch" :title="rule.enabled ? 'Đang chạy' : 'Đang tắt'"
            ><input
              type="checkbox"
              :checked="rule.enabled"
              :disabled="busy"
              :aria-label="`Bật/tắt ${rule.name}`"
              @change="toggle(rule)" /><span
          /></label>
        </div>
        <small class="flow-card-when" :class="rule.enabled ? 'on' : 'off'">
          <template v-if="rule.enabled && rule.scope === 'attached'"
            >📎 Chạy cho {{ rule.attached_count }} công việc được gắn, mỗi khi
            <strong>{{ triggerLabel[rule.trigger] ?? rule.trigger }}</strong></template
          >
          <template v-else-if="rule.enabled"
            >⚡ Tự chạy mỗi khi <strong>{{ triggerLabel[rule.trigger] ?? rule.trigger }}</strong></template
          >
          <template v-else
            >⏸ Đang tắt — sẽ không tự chạy khi
            <strong>{{ triggerLabel[rule.trigger] ?? rule.trigger }}</strong></template
          >
          · {{ rule.graph.nodes.length }} bước
        </small>
        <div class="flow-card-foot">
          <StatusBadge v-if="rule.last_run" :status="rule.last_run.state" />
          <small v-if="rule.last_run" class="muted">{{ formatDate(rule.last_run.created_at, true) }}</small>
          <small v-else class="muted">Chưa chạy lần nào</small>
          <RouterLink :to="`/automations/${rule.id}`" class="button ghost small" style="margin-left: auto"
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
      Triển khai chưa cho phép gọi ra ngoài. Quản trị hệ thống cần đặt
      <code>AUTOMATION_ALLOWED_HOSTS</code> với danh sách máy chủ được phép.
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

  <ModalDialog v-if="showTemplates" title="Tạo luồng mới" wide @close="showTemplates = false">
    <p class="muted" style="margin-bottom: 16px">Chọn một mẫu để bắt đầu; mọi bước đều chỉnh được trên canvas.</p>
    <div class="template-grid">
      <button
        v-for="template in TEMPLATES"
        :key="template.key"
        class="template-card"
        @click="router.push({ path: '/automations/new', query: { template: template.key } })"
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
  <p class="muted" style="margin-top: 18px; font-size: 13px">
    <Workflow :size="14" style="vertical-align: -2px" /> Mỗi sự kiện chỉ kích hoạt một luồng một lần; luồng không tự
    kích hoạt lại chính nó, chuỗi luồng dừng ở độ sâu 3.
  </p>
</template>
