<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import {
  CheckCircle2,
  ChevronDown,
  ClipboardList,
  FlaskConical,
  GitCompare,
  PackageOpen,
  Paperclip,
  Play,
  Plus,
  Rocket,
  ShieldCheck,
  Users,
  XCircle,
} from 'lucide-vue-next'
import { api } from '../api'
import { toast } from '../ui/toast'
import { useSession } from '../stores/session'
import { errorText, formatDate, newIntent, type Page } from '@dx/web-shared/api.ts'
import type { FormTemplate, User } from '@dx/web-shared/types.ts'
import StatePanel from '@dx/web-shared/components/StatePanel.vue'
import ProcessDiagram from '../packages/ProcessDiagram.vue'
import ScenarioEditor from '../packages/ScenarioEditor.vue'
import PackageDialog from '../packages/PackageDialog.vue'
import {
  DECISION_LABEL,
  ERROR_LABEL,
  ROLE_LABEL,
  VERSION_STATE,
  choicesFrom,
  latestReports,
  pathStops,
  readiness,
} from '../packages/model'
import type { PackageVersion, Report, ReportResult, Suite } from '../packages/model'
import '../packages/packages.css'

interface Package {
  id: string
  name: string
  description: string
  active_version_id: string | null
  allowed_roles: string[]
  created_at: string
}
interface VersionDiff {
  from_version: number
  to_version: number
  form_changed: boolean
  fields: { key: string; before: { label: string } | null; after: { label: string } | null }[]
  approval_steps: { before: PackageVersion['approval_steps']; after: PackageVersion['approval_steps'] } | null
  required_file_count: { before: number; after: number } | null
}
const session = useSession()
const client = useQueryClient()
const canManage = computed(() => session.can('forms.manage'))
const packages = useQuery({
  queryKey: ['business-packages'],
  queryFn: () => api.request<Page<Package>>('/business-packages'),
})
const forms = useQuery({ queryKey: ['forms'], queryFn: () => api.request<Page<FormTemplate>>('/forms') })
const users = useQuery({ queryKey: ['users'], queryFn: () => api.request<Page<User>>('/users') })
function userName(id: string) {
  return users.data.value?.items.find((u) => u.id === id)?.display_name ?? 'Người dùng đã khóa'
}
const selectedPackageId = ref('')
const selectedVersionId = ref('')
const versions = useQuery({
  queryKey: computed(() => ['business-package-versions', selectedPackageId.value]),
  queryFn: () => api.request<Page<PackageVersion>>(`/business-packages/${selectedPackageId.value}/versions`),
  enabled: computed(() => !!selectedPackageId.value),
})
const suites = useQuery({
  queryKey: computed(() => ['simulation-suites', selectedVersionId.value]),
  queryFn: () => api.request<Page<Suite>>(`/package-versions/${selectedVersionId.value}/test-suites`),
  enabled: computed(() => canManage.value && !!selectedVersionId.value),
})
const reports = useQuery({
  queryKey: computed(() => ['simulation-reports', selectedVersionId.value]),
  queryFn: () => api.request<Page<Report>>(`/package-versions/${selectedVersionId.value}/simulation-reports`),
  enabled: computed(() => canManage.value && !!selectedVersionId.value),
})
watch(
  () => packages.data.value?.items,
  (items) => {
    if (items?.length && !items.some((p) => p.id === selectedPackageId.value)) selectedPackageId.value = items[0].id
  },
)
watch(
  () => versions.data.value?.items,
  (items) => {
    if (items?.length && !items.some((v) => v.id === selectedVersionId.value))
      selectedVersionId.value = items.at(-1)!.id
  },
)
watch(selectedPackageId, () => {
  selectedVersionId.value = ''
  tab.value = 'process'
})
const selectedPackage = computed(() => packages.data.value?.items.find((p) => p.id === selectedPackageId.value))
const selectedVersion = computed(() => versions.data.value?.items.find((v) => v.id === selectedVersionId.value))
const versionForm = computed(() => forms.data.value?.items.find((f) => f.id === selectedVersion.value?.form_id))
const previousVersion = computed(
  () => versions.data.value?.items.filter((v) => v.version_no < (selectedVersion.value?.version_no ?? 0)).at(-1),
)
const versionDiff = useQuery({
  queryKey: computed(() => ['package-version-diff', selectedVersionId.value, previousVersion.value?.id]),
  queryFn: () =>
    api.request<VersionDiff>(`/package-versions/${selectedVersionId.value}/diff?against_id=${previousVersion.value!.id}`),
  enabled: computed(() => !!selectedVersionId.value && !!previousVersion.value),
})
const state = computed(() =>
  selectedVersion.value
    ? readiness(selectedVersion.value, suites.data.value?.items ?? [], reports.data.value?.items ?? [])
    : null,
)
const latest = computed(() =>
  selectedVersion.value ? latestReports(reports.data.value?.items ?? [], selectedVersion.value.config_hash) : new Map(),
)
const currentSuites = computed(() =>
  (suites.data.value?.items ?? []).filter((s) => s.config_hash === selectedVersion.value?.config_hash),
)
const staleSuites = computed(() =>
  (suites.data.value?.items ?? []).filter((s) => s.config_hash !== selectedVersion.value?.config_hash),
)
const tab = ref<'process' | 'tests' | 'changes'>('process')
const dialog = ref<'package' | 'version' | null>(null)
const busy = ref(false)
const error = ref('')
const notice = ref('')
const expanded = ref<string | null>(null)
const editor = ref<InstanceType<typeof ScenarioEditor> | null>(null)
async function action(run: () => Promise<void>, done?: string) {
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    await run()
    if (done) toast.success(done)
  } catch (cause) {
    error.value = errorText(cause)
  } finally {
    busy.value = false
  }
}
async function refreshVersion() {
  await client.invalidateQueries({ queryKey: ['business-package-versions', selectedPackageId.value] })
  await client.invalidateQueries({ queryKey: ['simulation-suites', selectedVersionId.value] })
  await client.invalidateQueries({ queryKey: ['simulation-reports', selectedVersionId.value] })
}
function validateVersion() {
  return action(async () => {
    await api.request(`/package-versions/${selectedVersionId.value}/validate`, {
      method: 'POST',
      body: JSON.stringify({ expected_revision: selectedVersion.value!.revision }),
    })
    await refreshVersion()
    tab.value = 'tests'
  }, 'Cấu hình hợp lệ. Tiếp theo: tạo và chạy kịch bản thử.')
}
function runSuite(suiteId: string) {
  return action(async () => {
    const report = await api.request<Report>(
      `/package-versions/${selectedVersionId.value}/simulate?suite_id=${encodeURIComponent(suiteId)}`,
      { method: 'POST', headers: { 'Idempotency-Key': newIntent() } },
    )
    await refreshVersion()
    expanded.value = suiteId
    if (!report.passed) error.value = 'Có kịch bản chưa đạt — xem chi tiết bên dưới.'
  })
}
async function runAll() {
  for (const suite of currentSuites.value) await runSuite(suite.id)
}
function publish() {
  return action(async () => {
    await api.request(`/package-versions/${selectedVersionId.value}/publish`, {
      method: 'POST',
      body: JSON.stringify({ expected_revision: selectedVersion.value!.revision }),
    })
    await refreshVersion()
    await client.invalidateQueries({ queryKey: ['business-packages'] })
  }, 'Đã phát hành. Hồ sơ mới tạo từ biểu mẫu này sẽ dùng phiên bản vừa phát hành.')
}
async function created(packageId: string) {
  dialog.value = null
  await client.invalidateQueries({ queryKey: ['business-packages'] })
  if (packageId !== selectedPackageId.value) selectedPackageId.value = packageId
  else await refreshVersion()
  selectedVersionId.value = ''
  toast.success('Đã tạo bản nháp. Bước tiếp theo: kiểm tra cấu hình.')
}
function reuseSuite(suite: Suite) {
  tab.value = 'tests'
  editor.value?.load(suite.cases)
}
function resultPath(result: ReportResult, which: 'expected_path' | 'actual_path') {
  const evidence = (result as ReportResult & { result?: { routing_evidence?: { selected: boolean; label: string }[] } })
    .result?.routing_evidence
  const labels = evidence?.filter((e) => e.selected).map((e) => e.label) ?? []
  return pathStops(result[which] ?? [], labels)
    .map((s) => s.label)
    .join(' → ')
}
const stages = computed(() => {
  const version = selectedVersion.value
  const ready = state.value
  if (!version || !ready) return []
  const published = version.state === 'published'
  return [
    { key: 'draft', title: 'Bản nháp', hint: 'Cấu hình đã ghim', done: true },
    { key: 'validate', title: 'Kiểm tra cấu hình', hint: 'Người duyệt, đồ thị', done: ready.validated },
    {
      key: 'test',
      title: 'Chạy thử đạt',
      hint: ready.hasSuites ? `${currentSuites.value.length} bộ kịch bản` : 'Chưa có kịch bản',
      done: published || ready.allPassed,
    },
    { key: 'publish', title: 'Phát hành', hint: published ? 'Đang dùng' : 'Áp dụng cho hồ sơ mới', done: published },
  ]
})
const currentStage = computed(() => stages.value.findIndex((s) => !s.done))
</script>

<template>
  <header class="page-head">
    <div>
      <span class="eyebrow">THIẾT KẾ QUY TRÌNH</span>
      <h1>Gói nghiệp vụ</h1>
      <p>Mỗi gói quy định một loại hồ sơ: biểu mẫu, ai duyệt theo thứ tự nào, cần tài liệu gì. Chạy thử trước khi áp dụng.</p>
    </div>
    <div v-if="canManage" class="page-actions">
      <button class="button" @click="dialog = 'package'"><Plus :size="18" />Tạo gói</button>
    </div>
  </header>
  <div v-if="error" class="notice error error-inline" role="alert">
    <XCircle :size="18" /><span>{{ error }}</span>
  </div>
  <div v-if="notice" class="notice success error-inline" role="status">
    <CheckCircle2 :size="18" /><span>{{ notice }}</span>
  </div>
  <section v-if="packages.isPending.value || packages.error.value || !packages.data.value?.items.length" class="card">
    <StatePanel
      :loading="packages.isPending.value"
      :error="packages.error.value"
      :empty="packages.data.value?.items.length === 0"
      title="Chưa có gói nghiệp vụ"
      description="Tạo gói từ một biểu mẫu đã phát hành để quy định cách xử lý một loại hồ sơ."
      @retry="packages.refetch()"
      ><button v-if="canManage" class="button small" @click="dialog = 'package'">
        <Plus :size="16" />Tạo gói
      </button></StatePanel
    >
  </section>
  <div v-else class="pkg-layout">
    <aside class="pkg-list" aria-label="Danh sách gói">
      <button
        v-for="item in packages.data.value?.items"
        :key="item.id"
        class="pkg-item"
        :class="{ active: item.id === selectedPackageId }"
        :title="item.name"
        @click="selectedPackageId = item.id"
      >
        <span class="pkg-item-icon"><PackageOpen :size="18" /></span>
        <span class="grow">
          <strong>{{ item.name }}</strong>
          <small>{{ item.description || 'Chưa có mô tả' }}</small>
        </span>
        <span class="status-badge" :class="item.active_version_id ? 'status-published' : 'status-draft'"
          ><span class="status-dot" />{{ item.active_version_id ? 'Đang dùng' : 'Nháp' }}</span
        >
      </button>
    </aside>

    <section v-if="selectedPackage" class="card pkg-detail">
      <header class="pkg-detail-head">
        <div class="grow">
          <h2>{{ selectedPackage.name }}</h2>
          <p class="muted">{{ selectedPackage.description || 'Chưa có mô tả.' }}</p>
          <div class="pkg-meta">
            <span><Users :size="14" />
              {{ selectedPackage.allowed_roles.length ? selectedPackage.allowed_roles.map((r) => ROLE_LABEL[r] ?? r).join(', ') : 'Mọi vai trò có quyền tạo hồ sơ' }}</span>
            <span v-if="selectedVersion"><Paperclip :size="14" /> Tối thiểu {{ selectedVersion.required_file_count }} tài liệu</span>
            <span v-if="versionForm"><ClipboardList :size="14" /> Biểu mẫu: {{ versionForm.name }}</span>
          </div>
        </div>
        <button v-if="canManage" class="button secondary small" @click="dialog = 'version'">
          <Plus :size="15" />Phiên bản mới
        </button>
      </header>

      <div class="version-chips" role="tablist" aria-label="Phiên bản">
        <button
          v-for="item in versions.data.value?.items"
          :key="item.id"
          role="tab"
          :aria-selected="item.id === selectedVersionId"
          class="version-chip"
          :class="[item.state, { active: item.id === selectedVersionId }]"
          @click="selectedVersionId = item.id"
        >
          v{{ item.version_no }} · {{ VERSION_STATE[item.state] ?? item.state }}
        </button>
      </div>

      <template v-if="selectedVersion && state">
        <ol v-if="canManage" class="lifecycle">
          <li
            v-for="(stage, index) in stages"
            :key="stage.key"
            :class="{ done: stage.done, current: index === currentStage }"
          >
            <span class="lifecycle-dot">{{ stage.done ? '✓' : index + 1 }}</span>
            <div>
              <strong>{{ stage.title }}</strong><small>{{ stage.hint }}</small>
            </div>
          </li>
        </ol>
        <div v-if="canManage && selectedVersion.state !== 'published'" class="next-action">
          <template v-if="selectedVersion.state === 'draft'">
            <span>Kiểm tra người duyệt còn hoạt động và đồ thị quy trình hợp lệ.</span>
            <button class="button" :disabled="busy" @click="validateVersion">
              <ShieldCheck :size="16" />Kiểm tra cấu hình
            </button>
          </template>
          <template v-else-if="!state.allPassed">
            <span>{{ state.blocker }}</span>
            <button v-if="state.hasSuites" class="button" :disabled="busy" @click="runAll">
              <Play :size="16" />Chạy tất cả kịch bản
            </button>
            <button v-else class="button" @click="tab = 'tests'"><FlaskConical :size="16" />Soạn kịch bản</button>
          </template>
          <template v-else>
            <span>Mọi kịch bản đều đạt trên đúng cấu hình này.</span>
            <button class="button" :disabled="busy || !state.canPublish" @click="publish">
              <Rocket :size="16" />Phát hành phiên bản
            </button>
          </template>
        </div>
        <div v-else-if="selectedVersion.state === 'published'" class="notice success" style="margin: 0 22px 4px">
          <CheckCircle2 :size="18" /><span
            >Phiên bản này đang được dùng cho hồ sơ mới. Muốn thay đổi, tạo <strong>phiên bản mới</strong> — hồ sơ cũ
            vẫn giữ phiên bản đã chọn.</span
          >
        </div>

        <div class="tabs pkg-tabs">
          <button class="tab" :class="{ active: tab === 'process' }" @click="tab = 'process'">
            <ClipboardList :size="15" />Quy trình
          </button>
          <button v-if="canManage" class="tab" :class="{ active: tab === 'tests' }" @click="tab = 'tests'">
            <FlaskConical :size="15" />Chạy thử
            <span v-if="state.hasSuites" class="tab-count" :class="state.allPassed ? 'ok' : 'bad'">{{
              currentSuites.length
            }}</span>
          </button>
          <button v-if="previousVersion" class="tab" :class="{ active: tab === 'changes' }" @click="tab = 'changes'">
            <GitCompare :size="15" />So với v{{ previousVersion.version_no }}
          </button>
        </div>

        <div v-if="tab === 'process'" class="pkg-pane">
          <ProcessDiagram
            :steps="selectedVersion.approval_steps"
            :fields="versionForm?.fields ?? []"
            :required-files="selectedVersion.required_file_count"
            :user-name="userName"
          />
          <div v-if="versionForm" class="form-fields-preview">
            <span class="section-label">Thông tin người trình phải nhập</span>
            <div class="field-chips">
              <span v-for="field in versionForm.fields" :key="field.key" class="tag"
                >{{ field.label }}<b v-if="field.required" class="required"> *</b></span
              >
            </div>
          </div>
          <small class="muted">Tạo lúc {{ formatDate(selectedVersion.created_at, true) }}</small>
        </div>

        <div v-else-if="tab === 'tests'" class="pkg-pane">
          <div v-if="!currentSuites.length && !staleSuites.length" class="muted" style="font-size: 14px">
            Chưa có bộ kịch bản. Soạn ít nhất một kịch bản bên dưới: hồ sơ đi hết quy trình, hồ sơ rẽ nhánh theo điều
            kiện, hồ sơ thiếu tài liệu…
          </div>
          <article v-for="suite in currentSuites" :key="suite.id" class="suite-card">
            <header>
              <span
                class="status-badge"
                :class="latest.get(suite.id) ? (latest.get(suite.id)!.passed ? 'status-succeeded' : 'status-failed') : 'status-pending'"
                ><span class="status-dot" />{{
                  latest.get(suite.id) ? (latest.get(suite.id)!.passed ? 'Đạt' : 'Chưa đạt') : 'Chưa chạy'
                }}</span
              >
              <span class="grow"
                ><strong>{{ suite.cases.length }} kịch bản</strong
                ><small>{{ suite.cases.map((c) => c.name).join(' · ') }}</small></span
              >
              <button
                v-if="selectedVersion.state !== 'published'"
                class="button secondary small"
                :disabled="busy || selectedVersion.state === 'draft'"
                :title="selectedVersion.state === 'draft' ? 'Kiểm tra cấu hình trước' : ''"
                @click="runSuite(suite.id)"
              >
                <Play :size="14" />Chạy
              </button>
              <button
                class="icon-button"
                :aria-label="expanded === suite.id ? 'Thu gọn' : 'Xem chi tiết'"
                @click="expanded = expanded === suite.id ? null : suite.id"
              >
                <ChevronDown :size="16" :style="{ transform: expanded === suite.id ? 'rotate(180deg)' : '' }" />
              </button>
            </header>
            <div v-if="expanded === suite.id" class="suite-results">
              <table>
                <thead>
                  <tr><th>Kịch bản</th><th>Quyết định</th><th>Kỳ vọng</th><th>Kết quả</th></tr>
                </thead>
                <tbody>
                  <tr v-for="fixture in suite.cases" :key="fixture.name">
                    <td><strong>{{ fixture.name }}</strong><small class="muted"> · {{ fixture.file_count }} tài liệu</small></td>
                    <td class="muted">
                      {{ choicesFrom(fixture.decisions, Object.keys(fixture.decisions).length).map((d) => DECISION_LABEL[d]).join(', ') || '—' }}
                    </td>
                    <td>
                      {{ fixture.expected_error_code ? `Bị chặn: ${ERROR_LABEL[fixture.expected_error_code]}` : pathStops(fixture.expected_path, []).map((s) => s.label).join(' → ') }}
                    </td>
                    <td>
                      <template v-for="result in latest.get(suite.id)?.results.filter((r: ReportResult) => r.name === fixture.name)" :key="result.name">
                        <span :class="result.passed ? 'pass-text' : 'overdue-text'">{{ result.passed ? '✓ Đúng' : '✗ Sai' }}</span>
                        <small v-if="!result.passed" class="muted" style="display: block">
                          {{ result.error ? result.error.detail : `Thực tế: ${resultPath(result, 'actual_path')}` }}
                        </small>
                      </template>
                      <span v-if="!latest.get(suite.id)" class="muted">—</span>
                    </td>
                  </tr>
                </tbody>
              </table>
              <button v-if="selectedVersion.state !== 'published'" class="button ghost small" @click="reuseSuite(suite)">
                Sửa lại thành bộ mới
              </button>
            </div>
          </article>
          <details v-if="staleSuites.length" class="stale-suites">
            <summary>{{ staleSuites.length }} bộ kịch bản của cấu hình cũ (không tính khi phát hành)</summary>
            <div v-for="suite in staleSuites" :key="suite.id" class="list-row">
              <div class="grow"><p>{{ suite.cases.map((c) => c.name).join(' · ') }}</p></div>
              <button class="button ghost small" @click="reuseSuite(suite)">Dùng lại</button>
            </div>
          </details>
          <template v-if="selectedVersion.state !== 'published'">
            <h3 class="pkg-subhead"><FlaskConical :size="16" /> Soạn bộ kịch bản mới</h3>
            <ScenarioEditor
              v-if="versionForm"
              ref="editor"
              :version-id="selectedVersion.id"
              :fields="versionForm.fields"
              :steps="selectedVersion.approval_steps"
              :required-files="selectedVersion.required_file_count"
              :user-name="userName"
              @saved="refreshVersion().then(() => toast.success('Đã lưu bộ kịch bản. Bấm Chạy để kiểm chứng.'))"
            />
          </template>
        </div>

        <div v-else-if="tab === 'changes' && versionDiff.data.value" class="pkg-pane">
          <p v-if="versionDiff.data.value.form_changed" class="notice">Phiên bản này dùng biểu mẫu khác.</p>
          <p v-if="versionDiff.data.value.required_file_count">
            Tài liệu tối thiểu:
            <s>{{ versionDiff.data.value.required_file_count.before }}</s> →
            <strong>{{ versionDiff.data.value.required_file_count.after }}</strong>
          </p>
          <div v-if="versionDiff.data.value.fields.length">
            <span class="section-label">Trường thông tin</span>
            <div class="field-chips">
              <span v-for="field in versionDiff.data.value.fields" :key="field.key" class="tag" :class="!field.before ? 'added' : !field.after ? 'removed' : 'changed'">
                {{ (field.after ?? field.before)?.label ?? field.key }} ·
                {{ !field.before ? 'thêm mới' : !field.after ? 'đã bỏ' : 'đã sửa' }}
              </span>
            </div>
          </div>
          <div v-if="versionDiff.data.value.approval_steps" class="diff-columns">
            <div>
              <span class="section-label">Quy trình v{{ versionDiff.data.value.from_version }}</span>
              <ProcessDiagram :steps="versionDiff.data.value.approval_steps.before" :fields="versionForm?.fields ?? []" :required-files="previousVersion!.required_file_count" :user-name="userName" />
            </div>
            <div>
              <span class="section-label">Quy trình v{{ versionDiff.data.value.to_version }}</span>
              <ProcessDiagram :steps="versionDiff.data.value.approval_steps.after" :fields="versionForm?.fields ?? []" :required-files="selectedVersion.required_file_count" :user-name="userName" />
            </div>
          </div>
          <p
            v-if="!versionDiff.data.value.form_changed && !versionDiff.data.value.required_file_count && !versionDiff.data.value.approval_steps && !versionDiff.data.value.fields.length"
            class="muted"
          >
            Không có thay đổi cấu hình so với v{{ versionDiff.data.value.from_version }}.
          </p>
        </div>
      </template>
      <StatePanel
        v-else
        :loading="versions.isPending.value"
        :error="versions.error.value"
        :empty="versions.data.value?.items.length === 0"
        title="Gói chưa có phiên bản"
        @retry="versions.refetch()"
      />
    </section>
  </div>

  <PackageDialog
    v-if="dialog"
    :mode="dialog"
    :package-id="selectedPackageId"
    :forms="(forms.data.value?.items ?? []).filter((f) => !f.state || f.state === 'published')"
    :templates="(packages.data.value?.items ?? []).filter((p) => p.active_version_id)"
    :initial-form-id="dialog === 'version' ? selectedVersion?.form_id : undefined"
    :initial-files="dialog === 'version' ? selectedVersion?.required_file_count : 0"
    :user-name="userName"
    @close="dialog = null"
    @created="created"
  />
</template>
