<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useUnsavedGuard } from '../ui/unsaved'
import { Ban, CheckCircle2, Copy, Eye, Plus, Save, Trash2 } from 'lucide-vue-next'
import { api } from '../api'
import { ApiError, errorText, newIntent } from '@dx/web-shared/api.ts'
import type { ApprovalStep, FormField } from '@dx/web-shared/types.ts'
import { initialPayload } from '@dx/web-shared/forms.ts'
import SchemaForm from '@dx/web-shared/components/SchemaForm.vue'
import ProcessDiagram from './ProcessDiagram.vue'
import {
  DECISION_LABEL,
  ERROR_LABEL,
  choicesFrom,
  decisionsFor,
  pathStops,
} from './model'
import type { Decision, ErrorCode, Fixture, Preview } from './model'
const props = defineProps<{
  versionId: string
  fields: FormField[]
  steps: ApprovalStep[]
  requiredFiles: number
  userName: (id: string) => string
}>()
const emit = defineEmits<{ saved: [] }>()

interface Draft {
  key: string
  name: string
  payload: Record<string, unknown>
  choices: Decision[]
  fileCount: number
  expectedPath: string[]
  expectedLabels: string[]
  expectedError: ErrorCode | null
  /** Inputs the expectation was taken from; editing them afterwards makes it stale. */
  expectedFor: string
}
function blank(index: number): Draft {
  return {
    key: newIntent(),
    name: `Kịch bản ${index}`,
    payload: initialPayload(props.fields),
    choices: props.steps.map(() => 'approve'),
    fileCount: props.requiredFiles,
    expectedPath: [],
    expectedLabels: [],
    expectedError: null,
    expectedFor: '',
  }
}
const drafts = ref<Draft[]>([blank(1)])
const dirty = computed(
  () =>
    drafts.value.length > 1 ||
    drafts.value.some(
      (draft) =>
        !!draft.expectedFor ||
        JSON.stringify(draft.payload) !== JSON.stringify(initialPayload(props.fields)),
    ),
)
useUnsavedGuard(dirty)
const activeKey = ref(drafts.value[0].key)
const active = computed(() => drafts.value.find((d) => d.key === activeKey.value) ?? drafts.value[0])
watch(
  () => props.versionId,
  () => {
    drafts.value = [blank(1)]
    activeKey.value = drafts.value[0].key
    preview.value = null
  },
)
function inputs(draft: Draft) {
  return JSON.stringify([draft.payload, draft.choices, draft.fileCount])
}
function hasExpectation(draft: Draft) {
  return (draft.expectedPath.length > 0 || !!draft.expectedError) && draft.expectedFor === inputs(draft)
}
function addDraft(copy = false) {
  const next = copy
    ? { ...structuredClone(active.value), key: newIntent(), name: `${active.value.name} (bản sao)`, expectedFor: '' }
    : blank(drafts.value.length + 1)
  drafts.value = [...drafts.value, next]
  activeKey.value = next.key
  preview.value = null
}
function removeDraft(key: string) {
  drafts.value = drafts.value.filter((d) => d.key !== key)
  if (!drafts.value.length) drafts.value = [blank(1)]
  activeKey.value = drafts.value[0].key
  preview.value = null
}
watch(activeKey, () => {
  preview.value = null
  previewError.value = null
})

const preview = ref<Preview | null>(null)
const previewError = ref<unknown>(null)
const busy = ref(false)
const error = ref<unknown>(null)
const selectedLabels = computed(
  () => preview.value?.routing_evidence.filter((e) => e.selected).map((e) => e.label) ?? [],
)
async function runPreview() {
  busy.value = true
  preview.value = null
  previewError.value = null
  try {
    preview.value = await api.request<Preview>(`/package-versions/${props.versionId}/preview`, {
      method: 'POST',
      body: JSON.stringify({
        payload: active.value.payload,
        decisions: decisionsFor(active.value.choices),
        file_count: active.value.fileCount,
      }),
    })
  } catch (cause) {
    previewError.value = cause
  } finally {
    busy.value = false
  }
}
const blockedCode = computed(() => {
  const cause = previewError.value
  return cause instanceof ApiError && cause.code in ERROR_LABEL ? (cause.code as ErrorCode) : null
})
function acceptPreview() {
  const draft = active.value
  if (preview.value) {
    draft.expectedPath = preview.value.path
    draft.expectedLabels = pathStops(preview.value.path, selectedLabels.value).map((s) => s.label)
    draft.expectedError = null
  } else if (blockedCode.value) {
    draft.expectedPath = []
    draft.expectedLabels = []
    draft.expectedError = blockedCode.value
  }
  draft.expectedFor = inputs(draft)
}
const ready = computed(() => drafts.value.every(hasExpectation))
async function saveSuite() {
  busy.value = true
  error.value = null
  try {
    const cases: Fixture[] = drafts.value.map((draft) => ({
      name: draft.name.trim() || 'Kịch bản',
      payload: draft.payload,
      decisions: decisionsFor(draft.choices),
      file_count: draft.fileCount,
      expected_path: draft.expectedError ? [] : draft.expectedPath,
      expected_error_code: draft.expectedError,
    }))
    await api.request(`/package-versions/${props.versionId}/test-suites`, {
      method: 'POST',
      headers: { 'Idempotency-Key': newIntent() },
      body: JSON.stringify({ cases }),
    })
    drafts.value = [blank(1)]
    activeKey.value = drafts.value[0].key
    emit('saved')
  } catch (cause) {
    error.value = cause
  } finally {
    busy.value = false
  }
}
defineExpose({ load: (fixtures: Fixture[]) => {
  drafts.value = fixtures.map((fixture) => {
    const draft: Draft = {
      ...blank(1),
      name: fixture.name,
      payload: structuredClone(fixture.payload),
      choices: choicesFrom(fixture.decisions, props.steps.length),
      fileCount: fixture.file_count,
      expectedPath: fixture.expected_path,
      expectedLabels: [],
      expectedError: fixture.expected_error_code,
    }
    // A saved expectation stays valid until the scenario's inputs are edited.
    draft.expectedFor = inputs(draft)
    return draft
  })
  activeKey.value = drafts.value[0].key
} })
</script>
<template>
  <div class="scenario-editor">
    <aside class="scenario-list" aria-label="Các kịch bản">
      <button
        v-for="draft in drafts"
        :key="draft.key"
        class="scenario-item"
        :class="{ active: draft.key === activeKey }"
        @click="activeKey = draft.key"
      >
        <CheckCircle2 v-if="hasExpectation(draft)" :size="15" class="ok" />
        <span v-else class="dot" />
        <span class="grow"
          ><strong>{{ draft.name || 'Kịch bản' }}</strong
          ><small>{{
            hasExpectation(draft)
              ? draft.expectedError
                ? `Kỳ vọng bị chặn: ${ERROR_LABEL[draft.expectedError]}`
                : `Kỳ vọng: ${draft.expectedLabels.join(' → ') || 'đã chốt đường đi'}`
              : 'Chưa chốt kỳ vọng'
          }}</small></span
        >
      </button>
      <div class="inline-actions">
        <button class="button ghost small" :disabled="drafts.length >= 20" @click="addDraft()">
          <Plus :size="14" />Thêm</button
        ><button class="button ghost small" :disabled="drafts.length >= 20" @click="addDraft(true)">
          <Copy :size="14" />Nhân bản
        </button>
      </div>
      <button class="button" :disabled="busy || !ready" @click="saveSuite">
        <Save :size="15" />Lưu bộ {{ drafts.length }} kịch bản
      </button>
      <small v-if="!ready" class="muted">Mỗi kịch bản cần được xem trước và chốt kỳ vọng.</small>
      <div v-if="error" class="notice error">{{ errorText(error) }}</div>
    </aside>
    <div class="scenario-body">
      <div class="scenario-head">
        <input v-model="active.name" class="scenario-name" aria-label="Tên kịch bản" maxlength="120" />
        <button class="icon-button" title="Xóa kịch bản" aria-label="Xóa kịch bản" @click="removeDraft(active.key)">
          <Trash2 :size="16" />
        </button>
      </div>
      <section>
        <span class="section-label">1. Dữ liệu hồ sơ mẫu</span>
        <SchemaForm v-model="active.payload" :fields="fields" />
      </section>
      <section class="scenario-row">
        <div class="field">
          <label for="scenario-files">Số tài liệu đính kèm</label
          ><input id="scenario-files" v-model.number="active.fileCount" type="number" min="0" max="30" />
          <small>Gói yêu cầu tối thiểu {{ requiredFiles }}.</small>
        </div>
        <div class="field grow">
          <label>2. Người duyệt sẽ quyết định</label>
          <div class="decision-list">
            <div v-for="(_, index) in active.choices" :key="index" class="decision-item">
              <span>Lượt {{ index + 1 }}</span>
              <div class="segmented">
                <button
                  v-for="(label, value) in DECISION_LABEL"
                  :key="value"
                  type="button"
                  :class="{ active: active.choices[index] === value, [value]: true }"
                  @click="active.choices[index] = value"
                >
                  {{ label }}
                </button>
              </div>
            </div>
          </div>
          <small>Lượt duyệt tính theo các bước thực sự áp dụng cho hồ sơ này (bước có điều kiện có thể bị bỏ qua).</small>
        </div>
      </section>
      <section>
        <div class="inline-actions">
          <span class="section-label" style="margin: 0">3. Xem trước và chốt kỳ vọng</span>
          <button class="button secondary small" :disabled="busy" @click="runPreview">
            <Eye :size="15" />{{ busy ? 'Đang chạy…' : 'Xem trước' }}
          </button>
        </div>
        <div v-if="preview" class="scenario-result">
          <div class="path-chips">
            <template v-for="(stop, index) in pathStops(preview.path, selectedLabels)" :key="stop.id"
              ><span v-if="index" class="path-arrow">→</span
              ><span class="path-chip" :class="stop.kind">{{ stop.label }}</span></template
            >
          </div>
          <ProcessDiagram
            :steps="steps"
            :fields="fields"
            :required-files="requiredFiles"
            :user-name="userName"
            :evidence="preview.routing_evidence"
          />
          <button class="button small" @click="acceptPreview">
            <CheckCircle2 :size="15" />Dùng kết quả này làm kỳ vọng
          </button>
        </div>
        <div v-else-if="previewError" class="scenario-result">
          <div class="notice warning">
            <Ban :size="18" /><span
              ><strong>Hồ sơ bị chặn:</strong> {{ errorText(previewError) }}</span
            >
          </div>
          <button v-if="blockedCode" class="button small" @click="acceptPreview">
            <CheckCircle2 :size="15" />Kỳ vọng hồ sơ bị chặn vì “{{ ERROR_LABEL[blockedCode] }}”
          </button>
        </div>
        <p v-else class="muted" style="font-size: 13px; margin-top: 8px">
          Chạy thử không tạo hồ sơ, nhiệm vụ hay thông báo thật.
        </p>
        <p v-if="!hasExpectation(active) && active.expectedFor" class="overdue-text" style="font-size: 13px">
          Dữ liệu đã đổi sau khi chốt kỳ vọng — hãy xem trước lại.
        </p>
      </section>
    </div>
  </div>
</template>
