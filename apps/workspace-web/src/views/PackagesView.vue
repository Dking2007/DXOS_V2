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
  Pencil,
  Plus,
  Rocket,
  ShieldCheck,
  Sparkles,
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
import ProcessWizard from '../processes/ProcessWizard.vue'
import type { ProcessDraft } from '../processes/ProcessWizard.vue'
import { useAi } from '../ai/useAi'
import PackageDialog from '../packages/PackageDialog.vue'
import {
  DECISION_LABEL,
  ERROR_LABEL,
  ROLE_LABEL,
  CHANGE_LABEL,
  VERSION_STATE,
  choicesFrom,
  impactHeadline,
  routeLabels,
  latestReports,
  pathStops,
  readiness,
} from '../packages/model'
import type { Impact, PackageVersion, Report, ReportResult, Suite } from '../packages/model'
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
// A suite written for either version can rehearse both, so offer the suites of the two together.
const previousSuites = useQuery({
  queryKey: computed(() => ['simulation-suites', previousVersion.value?.id]),
  queryFn: () => api.request<Page<Suite>>(`/package-versions/${previousVersion.value!.id}/test-suites`),
  enabled: computed(() => canManage.value && !!previousVersion.value),
})
const impactSuites = computed(() =>
  [...(suites.data.value?.items ?? []), ...(previousSuites.data.value?.items ?? [])].sort((a, b) =>
    b.created_at.localeCompare(a.created_at),
  ),
)
const impactSuiteId = ref('')
watch(impactSuites, (items) => {
  if (!items.some((s) => s.id === impactSuiteId.value)) impactSuiteId.value = items[0]?.id ?? ''
})
const impact = useQuery({
  queryKey: computed(() => ['package-version-impact', selectedVersionId.value, previousVersion.value?.id, impactSuiteId.value]),
  queryFn: () =>
    api.request<Impact>(
      `/package-versions/${selectedVersionId.value}/impact?against_id=${previousVersion.value!.id}&suite_id=${impactSuiteId.value}`,
    ),
  enabled: computed(() => canManage.value && !!selectedVersionId.value && !!previousVersion.value && !!impactSuiteId.value),
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
// Creating and changing a process happen in one wizard; the older dialog stays for turning a
// form made before processes existed into one.
const wizard = ref<{ mode: 'create' | 'revise'; initial?: ProcessDraft } | null>(null)
const legacyForms = useQuery({
  queryKey: ['processes', 'unpackaged-forms'],
  queryFn: () => api.request<Page<FormTemplate>>('/processes/unpackaged-forms'),
  enabled: canManage,
})
const legacyFormId = ref('')
function reviseProcess() {
  if (!selectedPackage.value || !selectedVersion.value || !versionForm.value) return
  wizard.value = {
    mode: 'revise',
    initial: {
      name: selectedPackage.value.name,
      description: versionForm.value.description ?? '',
      // The wizard copies these before editing them.
      fields: versionForm.value.fields,
      steps: selectedVersion.value.approval_steps,
      files: selectedVersion.value.required_file_count,
      roles: [...selectedPackage.value.allowed_roles],
    },
  }
}
async function saved(packageId: string) {
  wizard.value = null
  await client.invalidateQueries({ queryKey: ['business-packages'] })
  await client.invalidateQueries({ queryKey: ['forms'] })
  if (packageId !== selectedPackageId.value) selectedPackageId.value = packageId
  else await refreshVersion()
  selectedVersionId.value = ''
}
function convertForm(formId: string) {
  legacyFormId.value = formId
  dialog.value = 'package'
}
async function created(packageId: string) {
  legacyFormId.value = ''
  await client.invalidateQueries({ queryKey: ['processes', 'unpackaged-forms'] })
  dialog.value = null
  await client.invalidateQueries({ queryKey: ['business-packages'] })
  if (packageId !== selectedPackageId.value) selectedPackageId.value = packageId
  else await refreshVersion()
  selectedVersionId.value = ''
  toast.success('Đã tạo bản nháp. Bước tiếp theo: kiểm tra cấu hình.')
}
const ai = useAi()
const proposing = ref(false)
/** AI proposes scenarios; each comes with what the package does today, for the person to check. */
async function proposeScenarios() {
  if (!selectedVersion.value) return
  proposing.value = true
  try {
    const result = await api.request<{ fixtures: Suite['cases'] }>(
      `/ai/package-versions/${selectedVersion.value.id}/scenarios`,
      { method: 'POST' },
    )
    if (!result.fixtures.length) toast.error('AI chưa đề xuất được kịch bản dùng được.')
    else {
      editor.value?.load(result.fixtures)
      toast.success(`AI đề xuất ${result.fixtures.length} kịch bản. Xem lại kết quả mong đợi rồi lưu bộ.`)
    }
  } catch (cause) {
    toast.error(cause)
  } finally {
    proposing.value = false
  }
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
      title: 'Chạy thử (không bắt buộc)',
      hint: ready.hasSuites ? `${currentSuites.value.length} bộ kịch bản` : 'Bỏ qua được',
      done: published || (ready.validated && ready.allPassed),
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
      <h1>Quy trình</h1>
      <p>
        Mỗi quy trình quy định một loại hồ sơ: thông tin cần nhập, ai duyệt theo thứ tự nào và trong bao lâu, cần tài
        liệu gì. Tạo và sửa ở cùng một chỗ; mỗi lần sửa là một phiên bản mới, hồ sơ đã lập giữ quy trình cũ.
      </p>
    </div>
    <div v-if="canManage" class="page-actions">
      <button class="button" @click="wizard = { mode: 'create' }"><Plus :size="18" />Tạo quy trình</button>
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
      title="Chưa có quy trình nào"
      description="Tạo quy trình đầu tiên: thông tin cần nhập, các bước duyệt và thời hạn, tài liệu cần kèm."
      @retry="packages.refetch()"
      ><button v-if="canManage" class="button small" @click="wizard = { mode: 'create' }">
        <Plus :size="16" />Tạo quy trình
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
        <button v-if="canManage && versionForm" class="button secondary small" @click="reviseProcess">
          <Pencil :size="15" />Sửa quy trình
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
            >Phiên bản này đang được dùng cho hồ sơ mới. Muốn thay đổi, bấm <strong>Sửa quy trình</strong>: hệ thống tạo
            phiên bản mới, hồ sơ đã lập vẫn giữ phiên bản cũ.</span
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
            <h3 class="pkg-subhead"><FlaskConical :size="16" /> Soạn bộ kịch bản mới
              <button
                v-if="ai.on('package_scenarios')"
                class="button secondary small ai-action"
                style="margin-left: auto"
                :disabled="proposing"
                @click="proposeScenarios"
              >
                <Sparkles :size="14" />{{ proposing ? 'AI đang nghĩ…' : 'Gợi ý kịch bản bằng AI' }}
              </button></h3
            >
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
          <section v-if="canManage && previousVersion" class="impact" aria-labelledby="impact-title">
            <span id="impact-title" class="section-label">Tác động lên hồ sơ mẫu</span>
            <p v-if="!impactSuites.length" class="muted">
              Chưa có bộ thử. Tạo bộ thử ở thẻ Chạy thử để xem phiên bản này thay đổi gì với hồ sơ mẫu.
            </p>
            <template v-else>
              <label v-if="impactSuites.length > 1" class="impact-pick">
                Bộ thử
                <select v-model="impactSuiteId">
                  <option v-for="(suite, index) in impactSuites" :key="suite.id" :value="suite.id">
                    Bộ {{ impactSuites.length - index }} · {{ suite.cases.length }} hồ sơ mẫu · {{ formatDate(suite.created_at) }}
                  </option>
                </select>
              </label>
              <p v-if="impact.isPending.value" class="muted">Đang chạy thử hai phiên bản…</p>
              <p v-else-if="impact.error.value" class="notice" role="alert">{{ errorText(impact.error.value) }}</p>
              <template v-else-if="impact.data.value">
                <p class="impact-headline" :class="{ changed: impact.data.value.summary.changed }">
                  {{ impactHeadline(impact.data.value) }}
                </p>
                <p v-if="impact.data.value.summary.recipient_drift" class="notice">
                  Cơ cấu tổ chức đã đổi từ lần chạy thử trước: {{ impact.data.value.summary.recipient_drift }} hồ sơ mẫu
                  hiện có người nhận khác. Chạy lại bộ thử trước khi phát hành.
                </p>
                <ul class="impact-list">
                  <li v-for="item in impact.data.value.items" :key="item.name" :class="{ changed: item.changed }">
                    <div class="impact-name">
                      <strong>{{ item.name }}</strong>
                      <span class="tag" :class="item.changed ? 'changed' : ''">
                        {{ item.changed ? 'Đổi ' + item.changes.map((c) => CHANGE_LABEL[c]).join(', ') : 'Không đổi' }}
                      </span>
                    </div>
                    <dl v-if="item.changed" class="impact-compare">
                      <div><dt>v{{ impact.data.value.baseline.version_no }}</dt><dd>{{ routeLabels(item.baseline) }}</dd></div>
                      <div><dt>v{{ impact.data.value.candidate.version_no }}</dt><dd>{{ routeLabels(item.candidate) }}</dd></div>
                    </dl>
                  </li>
                </ul>
                <p class="muted">Chỉ chạy thử: không tạo việc, không gửi thông báo, không phát hành.</p>
              </template>
            </template>
          </section>
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

  <section v-if="canManage && legacyForms.data.value?.items.length" class="card" style="margin-top: 20px">
    <header class="card-header">
      <div>
        <h2>Biểu mẫu chưa thành quy trình</h2>
        <p class="muted" style="font-size: 13px; margin-top: 4px">
          Mẫu tạo trước khi có màn Quy trình. Hồ sơ vẫn dùng được; chuyển thành quy trình để quản lý phiên bản,
          tài liệu bắt buộc và chạy thử ở một chỗ.
        </p>
      </div>
    </header>
    <div v-for="form in legacyForms.data.value.items" :key="form.id" class="list-row">
      <div class="grow">
        <p>{{ form.name }}</p>
        <small>{{ form.fields.length }} trường · {{ form.approval_steps.length }} bước duyệt</small>
      </div>
      <button class="button secondary small" @click="convertForm(form.id)">Chuyển thành quy trình</button>
    </div>
  </section>
  <PackageDialog
    v-if="dialog"
    :mode="dialog"
    :package-id="selectedPackageId"
    :forms="(forms.data.value?.items ?? []).filter((f) => !f.state || f.state === 'published')"
    :templates="(packages.data.value?.items ?? []).filter((p) => p.active_version_id)"
    :initial-form-id="dialog === 'version' ? selectedVersion?.form_id : legacyFormId || undefined"
    :initial-files="dialog === 'version' ? selectedVersion?.required_file_count : 0"
    :user-name="userName"
    @close="dialog = null"
    @created="created"
  />
  <ProcessWizard
    v-if="wizard"
    :mode="wizard.mode"
    :package-id="selectedPackageId"
    :initial="wizard.initial"
    :users="users.data.value?.items ?? []"
    :user-name="userName"
    @close="wizard = null"
    @saved="saved"
  />
</template>
