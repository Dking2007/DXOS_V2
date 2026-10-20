<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { api } from '../api'
import { useSession } from '../stores/session'
import { errorText, newIntent, type Page } from '@dx/web-shared/api.ts'
import type { FormTemplate } from '@dx/web-shared/types.ts'
import StatePanel from '@dx/web-shared/components/StatePanel.vue'

interface Package {
  id: string
  name: string
  description: string
  active_version_id: string | null
}
interface Version {
  id: string
  package_id: string
  form_id: string
  version_no: number
  required_file_count: number
  state: string
  revision: number
  config_hash: string
}
interface Preview {
  execution_mode: string
  effects_performed: boolean
  path: string[]
  state: string
  assignees: { node_id: string; subject: string }[]
  routing_evidence: { label: string; selected: boolean; recipient: string | null; evaluated_value: unknown }[]
}
interface Suite {
  id: string
  cases: { name: string }[]
}
interface Report {
  id: string
  suite_id: string
  passed: boolean
  results: { name: string; passed: boolean; error?: { detail: string }; actual_path?: string[] }[]
}
interface VersionDiff {
  from_version: number
  to_version: number
  form_changed: boolean
  fields: { key: string; before: unknown; after: unknown }[]
  approval_steps: { before: unknown; after: unknown } | null
  required_file_count: { before: number; after: number } | null
}
const session = useSession()
const client = useQueryClient()
const canManage = computed(() => session.can('forms.manage'))
const packages = useQuery({ queryKey: ['business-packages'], queryFn: () => api.request<Page<Package>>('/business-packages') })
const forms = useQuery({ queryKey: ['forms'], queryFn: () => api.request<Page<FormTemplate>>('/forms') })
const selectedPackageId = ref('')
const selectedVersionId = ref('')
const versions = useQuery({
  queryKey: computed(() => ['business-package-versions', selectedPackageId.value]),
  queryFn: () => api.request<Page<Version>>(`/business-packages/${selectedPackageId.value}/versions`),
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
watch(() => packages.data.value?.items, items => {
  if (items?.length && !selectedPackageId.value) selectedPackageId.value = items[0].id
})
watch(() => versions.data.value?.items, items => {
  if (items?.length && !items.some(v => v.id === selectedVersionId.value))
    selectedVersionId.value = items.at(-1)!.id
})
const selectedVersion = computed(() => versions.data.value?.items.find(v => v.id === selectedVersionId.value))
const previousVersion = computed(() => versions.data.value?.items.filter(v => v.version_no < (selectedVersion.value?.version_no ?? 0)).at(-1))
const versionDiff = useQuery({
  queryKey: computed(() => ['package-version-diff', selectedVersionId.value, previousVersion.value?.id]),
  queryFn: () => api.request<VersionDiff>(`/package-versions/${selectedVersionId.value}/diff?against_id=${previousVersion.value!.id}`),
  enabled: computed(() => !!selectedVersionId.value && !!previousVersion.value),
})
const publishReady = computed(() => {
  const savedSuites = suites.data.value?.items ?? []
  const savedReports = reports.data.value?.items ?? []
  return savedSuites.length > 0 && savedSuites.every(suite => savedReports.find(report => report.suite_id === suite.id)?.passed)
})
const newName = ref('')
const newDescription = ref('')
const formId = ref('')
const requiredFileCount = ref(0)
const allowedRoles = ref<string[]>([])
const fixtureName = ref('Hồ sơ mẫu')
const payloadText = ref('{}')
const decisionsText = ref('{}')
const fixtureFileCount = ref(0)
const expectedErrorCode = ref('')
const expectedPathText = ref('[]')
const batchCasesText = ref('')
const preview = ref<Preview | null>(null)
const error = ref('')
const busy = ref(false)

function parseObject(value: string): Record<string, unknown> {
  const parsed: unknown = JSON.parse(value)
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) throw new Error('Cần nhập JSON object.')
  return parsed as Record<string, unknown>
}
function parsePath(): string[] {
  const parsed: unknown = JSON.parse(expectedPathText.value)
  if (!Array.isArray(parsed) || !parsed.length || !parsed.every(item => typeof item === 'string'))
    throw new Error('Đường đi kỳ vọng cần là mảng tên bước, ví dụ ["start", "review_0"].')
  return parsed
}
async function action(run: () => Promise<void>) {
  busy.value = true
  error.value = ''
  try { await run() } catch (cause) { error.value = errorText(cause) } finally { busy.value = false }
}
async function createPackage() {
  await action(async () => {
    const result = await api.request<Package>('/business-packages', {
      method: 'POST', headers: { 'Idempotency-Key': newIntent() },
      body: JSON.stringify({ name: newName.value, description: newDescription.value, form_id: formId.value,
        required_file_count: requiredFileCount.value, allowed_roles: allowedRoles.value }),
    })
    newName.value = ''
    selectedPackageId.value = result.id
    await client.invalidateQueries({ queryKey: ['business-packages'] })
  })
}
async function importTemplate(item: Package) {
  if (!item.active_version_id || !newName.value.trim()) return
  await action(async () => {
    const result = await api.request<Package>('/business-packages/from-template', {
      method: 'POST', headers: { 'Idempotency-Key': newIntent() },
      body: JSON.stringify({ version_id: item.active_version_id, name: newName.value.trim() }),
    })
    selectedPackageId.value = result.id
    newName.value = ''
    await client.invalidateQueries({ queryKey: ['business-packages'] })
  })
}
async function createVersion() {
  await action(async () => {
    await api.request(`/business-packages/${selectedPackageId.value}/versions`, {
      method: 'POST', headers: { 'Idempotency-Key': newIntent() },
      body: JSON.stringify({ form_id: formId.value, required_file_count: requiredFileCount.value }),
    })
    await client.invalidateQueries({ queryKey: ['business-package-versions', selectedPackageId.value] })
  })
}
async function validateVersion() {
  if (!selectedVersion.value) return
  await action(async () => {
    await api.request(`/package-versions/${selectedVersionId.value}/validate`, {
      method: 'POST', body: JSON.stringify({ expected_revision: selectedVersion.value!.revision }),
    })
    await client.invalidateQueries({ queryKey: ['business-package-versions', selectedPackageId.value] })
  })
}
async function runPreview() {
  await action(async () => {
    preview.value = await api.request<Preview>(`/package-versions/${selectedVersionId.value}/preview`, {
      method: 'POST', body: JSON.stringify({ payload: parseObject(payloadText.value), decisions: parseObject(decisionsText.value), file_count: fixtureFileCount.value }),
    })
    expectedPathText.value = JSON.stringify(preview.value.path)
  })
}
async function saveSuite() {
  await action(async () => {
    let cases: unknown[]
    if (batchCasesText.value.trim()) {
      const parsed: unknown = JSON.parse(batchCasesText.value)
      if (!Array.isArray(parsed) || !parsed.length || parsed.length > 20)
        throw new Error('Bộ thử cần từ 1 đến 20 hồ sơ mẫu.')
      cases = parsed
    } else {
      cases = [{ name: fixtureName.value, payload: parseObject(payloadText.value),
        decisions: parseObject(decisionsText.value), file_count: fixtureFileCount.value,
        expected_path: expectedErrorCode.value ? [] : parsePath(), expected_error_code: expectedErrorCode.value || null }]
    }
    await api.request(`/package-versions/${selectedVersionId.value}/test-suites`, {
      method: 'POST', headers: { 'Idempotency-Key': newIntent() },
      body: JSON.stringify({ cases }),
    })
    await client.invalidateQueries({ queryKey: ['simulation-suites', selectedVersionId.value] })
  })
}
async function runSuite(suiteId: string) {
  await action(async () => {
    await api.request(`/package-versions/${selectedVersionId.value}/simulate?suite_id=${encodeURIComponent(suiteId)}`, {
      method: 'POST', headers: { 'Idempotency-Key': newIntent() },
    })
    await client.invalidateQueries({ queryKey: ['simulation-reports', selectedVersionId.value] })
  })
}
async function publish() {
  if (!selectedVersion.value) return
  await action(async () => {
    await api.request(`/package-versions/${selectedVersionId.value}/publish`, {
      method: 'POST', body: JSON.stringify({ expected_revision: selectedVersion.value!.revision }),
    })
    await client.invalidateQueries({ queryKey: ['business-package-versions', selectedPackageId.value] })
    await client.invalidateQueries({ queryKey: ['business-packages'] })
    await client.invalidateQueries({ queryKey: ['business-packages', 'active'] })
  })
}
</script>

<template>
  <header class="page-head">
    <div><span class="eyebrow">THIẾT KẾ QUY TRÌNH</span><h1>Gói nghiệp vụ</h1>
      <p>Thiết kế → kiểm chứng → phát hành. Chạy thử không thực hiện hành động thật.</p></div>
  </header>
  <div v-if="error" class="notice error" role="alert">{{ error }}</div>
  <StatePanel :loading="packages.isPending.value" :error="packages.error.value"
    :empty="packages.data.value?.items.length === 0" title="Chưa có gói nghiệp vụ" @retry="packages.refetch()" />
  <section v-if="canManage" class="card" style="padding: 24px; margin-bottom: 20px">
    <h2>Tạo gói hoặc phiên bản mới</h2>
    <p class="muted">Tạo biểu mẫu và điều kiện duyệt trong <RouterLink to="/settings">Thiết lập</RouterLink>, rồi chọn mẫu ở đây.</p>
    <div class="form-grid" style="margin-top: 16px">
      <div class="field"><label for="package-name">Tên gói mới</label><input id="package-name" v-model="newName" placeholder="Ví dụ: Đề nghị mua sắm" /></div>
      <div class="field"><label for="package-form">Biểu mẫu đã phát hành</label><select id="package-form" v-model="formId">
        <option value="">Chọn biểu mẫu</option><option v-for="form in forms.data.value?.items" :key="form.id" :value="form.id">{{ form.name }}</option>
      </select></div>
      <div class="field"><label for="package-documents">Số tài liệu tối thiểu khi trình</label><input id="package-documents" v-model.number="requiredFileCount" type="number" min="0" max="30" /></div>
      <div class="field"><label for="package-roles">Vai trò được sử dụng (để trống: mọi vai trò)</label>
        <select id="package-roles" v-model="allowedRoles" multiple>
          <option value="staff">Nhân viên</option><option value="manager">Lãnh đạo phòng</option>
          <option value="director">Giám đốc</option><option value="technical_admin">Quản trị kỹ thuật</option>
        </select></div>
      <div class="field full-width"><label for="package-description">Mục đích</label><textarea id="package-description" v-model="newDescription" rows="2" /></div>
    </div>
    <div class="inline-actions" style="margin-top: 16px">
      <button class="button" :disabled="busy || !formId || !newName" @click="createPackage">Tạo gói</button>
      <button class="button secondary" :disabled="busy || !formId || !selectedPackageId" @click="createVersion">Tạo phiên bản cho gói đang chọn</button>
    </div>
  </section>
  <section v-if="canManage" class="card" style="padding: 24px; margin-bottom: 20px">
    <h2>Thư viện mẫu nội bộ</h2>
    <p class="muted">Nhập tên gói mới ở trên, rồi sao chép cấu hình đã phát hành thành bản nháp riêng để kiểm chứng lại.</p>
    <div v-for="item in packages.data.value?.items.filter(value => value.active_version_id)" :key="item.id" class="list-row">
      <div class="grow"><strong>{{ item.name }}</strong><small>{{ item.description }}</small></div>
      <button class="button secondary small" :disabled="busy || !newName.trim()" @click="importTemplate(item)">Sao chép làm gói mới</button>
    </div>
  </section>
  <section class="card" style="padding: 24px; margin-bottom: 20px">
    <div class="form-grid">
      <div class="field"><label for="package-select">Gói</label><select id="package-select" v-model="selectedPackageId">
        <option v-for="item in packages.data.value?.items" :key="item.id" :value="item.id">{{ item.name }}</option>
      </select></div>
      <div class="field"><label for="version-select">Phiên bản</label><select id="version-select" v-model="selectedVersionId">
        <option v-for="item in versions.data.value?.items" :key="item.id" :value="item.id">v{{ item.version_no }} · {{ item.state }}</option>
      </select></div>
    </div>
    <div v-if="selectedVersion" class="stack" style="margin-top: 20px">
      <p>Trạng thái: <strong>{{ selectedVersion.state }}</strong> · tài liệu tối thiểu: {{ selectedVersion.required_file_count }}</p>
      <small class="mono">Cấu hình: {{ selectedVersion.config_hash.slice(0, 16) }}…</small>
      <div v-if="canManage" class="inline-actions">
        <button class="button secondary" :disabled="busy || selectedVersion.state !== 'draft'" @click="validateVersion">Kiểm tra cấu hình</button>
        <button class="button" :disabled="busy || selectedVersion.state !== 'validated' || !publishReady" @click="publish">Phát hành phiên bản</button>
      </div>
    </div>
  </section>
  <section v-if="previousVersion && versionDiff.data.value" class="card" style="padding: 24px; margin-bottom: 20px">
    <h2>Thay đổi so với phiên bản {{ versionDiff.data.value.from_version }}</h2>
    <p v-if="versionDiff.data.value.form_changed">Biểu mẫu đã thay đổi.</p>
    <p v-if="versionDiff.data.value.required_file_count">Tài liệu tối thiểu: {{ versionDiff.data.value.required_file_count.before }} → {{ versionDiff.data.value.required_file_count.after }}</p>
    <div v-for="field in versionDiff.data.value.fields" :key="field.key" class="list-row">
      <strong>{{ field.key }}</strong><small>{{ field.before ? 'Đã sửa' : 'Đã thêm' }}{{ field.after ? '' : ' / đã xóa' }}</small>
      <details><summary>Xem cấu hình trường</summary><pre>{{ JSON.stringify(field, null, 2) }}</pre></details>
    </div>
    <details v-if="versionDiff.data.value.approval_steps"><summary>Các bước duyệt đã thay đổi</summary>
      <pre>{{ JSON.stringify(versionDiff.data.value.approval_steps, null, 2) }}</pre></details>
    <p v-if="!versionDiff.data.value.form_changed && !versionDiff.data.value.required_file_count && !versionDiff.data.value.approval_steps && !versionDiff.data.value.fields.length">Không có thay đổi cấu hình.</p>
  </section>
  <section v-if="selectedVersion && canManage" class="card" style="padding: 24px; margin-bottom: 20px">
    <span class="eyebrow">CHẠY THỬ — KHÔNG THỰC HIỆN HÀNH ĐỘNG THẬT</span><h2>Hồ sơ mẫu</h2>
    <div class="form-grid" style="margin-top: 16px">
      <div class="field"><label for="fixture-name">Tên kịch bản</label><input id="fixture-name" v-model="fixtureName" /></div>
      <div class="field"><label for="fixture-payload">Dữ liệu biểu mẫu (JSON)</label><textarea id="fixture-payload" v-model="payloadText" rows="5" /></div>
      <div class="field"><label for="fixture-decisions">Quyết định giả lập (JSON)</label><textarea id="fixture-decisions" v-model="decisionsText" rows="5" placeholder="{&quot;review_0&quot;:{&quot;decision&quot;:&quot;approve&quot;}}" /></div>
      <div class="field"><label for="fixture-file-count">Số tài liệu mẫu</label><input id="fixture-file-count" v-model.number="fixtureFileCount" type="number" min="0" max="30" /></div>
      <div class="field"><label for="fixture-error">Lỗi kỳ vọng</label><select id="fixture-error" v-model="expectedErrorCode">
        <option value="">Không có lỗi</option><option value="required_documents_missing">Thiếu tài liệu bắt buộc</option>
        <option value="approval_configuration_error">Không tìm thấy người duyệt</option><option value="self_approval_denied">Người tạo trùng người duyệt</option><option value="form_validation_error">Dữ liệu biểu mẫu không hợp lệ</option>
      </select></div>
      <div class="field"><label for="fixture-path">Đường đi kỳ vọng (JSON)</label><textarea id="fixture-path" v-model="expectedPathText" rows="5" /></div>
      <div class="field full-width"><label for="batch-cases">Nhiều hồ sơ mẫu (JSON, tùy chọn, tối đa 20)</label><textarea id="batch-cases" v-model="batchCasesText" rows="5" placeholder="[{&quot;name&quot;:&quot;SC01&quot;,&quot;payload&quot;:{},&quot;decisions&quot;:{},&quot;expected_path&quot;:[&quot;start&quot;]}]" /><small>Nếu nhập danh sách này, nút lưu bộ thử dùng danh sách thay cho hồ sơ mẫu phía trên.</small></div>
    </div>
    <div class="inline-actions" style="margin-top: 16px">
      <button class="button secondary" :disabled="busy" @click="runPreview">Xem đường đi giả lập</button>
      <button class="button" :disabled="busy" @click="saveSuite">Lưu kịch bản và kỳ vọng</button>
    </div>
    <div v-if="preview" class="notice" style="margin-top: 18px">
      <strong>Kết quả giả lập:</strong> {{ preview.path.join(' → ') }} · {{ preview.state }}
      <p v-for="step in preview.routing_evidence" :key="step.label">
        {{ step.label }}: {{ step.selected ? `chọn ${step.recipient}` : 'bỏ qua' }}
        <span v-if="step.evaluated_value !== null"> · giá trị xét: {{ step.evaluated_value }}</span>
      </p>
      <small>Không tạo hồ sơ, nhiệm vụ hoặc thông báo sản xuất.</small>
    </div>
    <div v-for="suite in suites.data.value?.items" :key="suite.id" class="list-row">
      <div class="grow">{{ suite.cases.map(item => item.name).join(', ') }}</div>
      <button class="button secondary small" :disabled="busy" @click="runSuite(suite.id)">Chạy bộ thử</button>
    </div>
    <div v-for="report in reports.data.value?.items" :key="report.id" class="list-row">
      <div class="grow"><strong>{{ report.passed ? 'Đạt' : 'Chưa đạt' }}</strong>
        <small v-for="item in report.results" :key="item.name">{{ item.name }}: {{ item.passed ? (item.error ? `đúng lỗi ${item.error.detail}` : 'đúng đường đi') : item.error?.detail || `đường đi ${item.actual_path?.join(' → ')}` }}</small>
      </div>
    </div>
  </section>
</template>
