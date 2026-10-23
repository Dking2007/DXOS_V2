<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import {
  ArrowRight,
  ChevronRight,
  FilePlus2,
  Files,
  Search,
} from 'lucide-vue-next'
import { api } from '../api'
import {
  ApiError,
  errorText,
  formatDate,
  newIntent,
  queryString,
} from '@dx/web-shared/api.ts'
import type { Page } from '@dx/web-shared/api.ts'
import type { CaseItem, DriveFile, FormTemplate, User } from '@dx/web-shared/types.ts'
import type { components } from '@dx/web-shared/generated/workspace-api.ts'
import { initialPayload, validatePayload } from '@dx/web-shared/forms.ts'
import StatePanel from '@dx/web-shared/components/StatePanel.vue'
import ModalDialog from '@dx/web-shared/components/ModalDialog.vue'
import { toast } from '../ui/toast'
import { useSession } from '../stores/session'
import { confirmDiscard } from '../ui/unsaved'
import StatusBadge from '@dx/web-shared/components/StatusBadge.vue'
import SchemaForm from '@dx/web-shared/components/SchemaForm.vue'
const route = useRoute()
const session = useSession()
const router = useRouter()
const queryClient = useQueryClient()
const status = ref('')
const search = ref('')
const cursor = ref<string | null>(null)
const cases = useQuery({
  queryKey: computed(() => ['cases', status.value, search.value, cursor.value]),
  queryFn: () =>
    api.request<Page<CaseItem>>(
      `/cases${queryString({ status: status.value, q: search.value, cursor: cursor.value })}`,
    ),
})
const forms = useQuery({
  queryKey: ['forms'],
  queryFn: () => api.request<Page<FormTemplate>>('/forms'),
})
interface ActivePackageVersion {
  id: string
  form_id: string
  version_no: number
  package_name: string
}
const activePackages = useQuery({
  queryKey: ['business-packages', 'active'],
  queryFn: () => api.request<Page<ActivePackageVersion>>('/business-packages/active-versions'),
})
const files = useQuery({
  queryKey: ['drive', 'case-picker'],
  queryFn: () => api.request<Page<DriveFile>>('/drive/files'),
})
const showCreate = ref(false)
const title = ref('')
const formId = ref('')
const packageVersionId = ref('')
const payload = ref<Record<string, unknown>>({})
const fileIds = ref<string[]>([])
const priority = ref<'low' | 'normal' | 'high' | 'urgent'>('normal')
const dueAt = ref('')
const assigneeId = ref('')
const errors = ref<Record<string, string>>({})
const error = ref<unknown>(null)
const busy = ref(false)
const intent = ref(newIntent())
const selectedForm = computed(() =>
  forms.data.value?.items.find((form) => form.id === formId.value),
)
const matchingPackages = computed(() =>
  activePackages.data.value?.items.filter((item) => item.form_id === formId.value) ?? [],
)
const members = useQuery({
  queryKey: ['users', 'assignees'],
  queryFn: () => api.request<Page<User>>('/users'),
})
watch(formId, () => {
  packageVersionId.value = ''
  payload.value = initialPayload(selectedForm.value?.fields ?? [])
  errors.value = {}
})
watch(matchingPackages, (items) => {
  if (!items.some((item) => item.id === packageVersionId.value))
    packageVersionId.value = items[0]?.id ?? ''
})
watch([status, search], () => {
  cursor.value = null
})
function openCreate() {
  showCreate.value = true
  error.value = null
  intent.value = newIntent()
  priority.value = 'normal'
  dueAt.value = ''
  assigneeId.value = ''
}
const createDirty = computed(
  () =>
    !!title.value.trim() ||
    fileIds.value.length > 0 ||
    JSON.stringify(payload.value) !== JSON.stringify(initialPayload(selectedForm.value?.fields ?? [])),
)
function closeCreate() {
  if (!busy.value && confirmDiscard(createDirty.value)) {
    showCreate.value = false
    if (route.query.create) router.replace('/cases')
  }
}
watch(
  () => route.query.create,
  (value) => {
    if (value && !showCreate.value) openCreate()
  },
  { immediate: true },
)
/** The local datetime input value as the timezone-aware instant the API requires. */
function dueInstant() {
  if (!dueAt.value) return null
  const parsed = new Date(dueAt.value)
  return Number.isNaN(parsed.getTime()) ? null : parsed.toISOString()
}
async function create() {
  if (!selectedForm.value) return
  errors.value = validatePayload(selectedForm.value.fields, payload.value)
  if (Object.keys(errors.value).length) return
  busy.value = true
  error.value = null
  try {
    const item = await api.request<CaseItem>('/cases', {
      method: 'POST',
      headers: { 'Idempotency-Key': intent.value },
      body: JSON.stringify({
        title: title.value,
        form_id: formId.value,
        package_version_id: packageVersionId.value || null,
        payload: payload.value,
        file_ids: fileIds.value,
        priority: priority.value,
        due_at: dueInstant(),
        assignee_id: assigneeId.value || null,
      } satisfies components['schemas']['CaseCreate']),
    })
    await queryClient.invalidateQueries({ queryKey: ['cases'] })
    showCreate.value = false
    toast.success('Đã tạo hồ sơ nháp. Kiểm tra lại rồi bấm “Chuyển duyệt”.')
    await router.push(`/cases/${item.id}`)
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
      <span class="eyebrow">HỒ SƠ ĐIỆN TỬ</span>
      <h1>Mọi hồ sơ, một dòng xử lý.</h1>
      <p>Theo dõi từ bản nháp đến quyết định cuối cùng.</p>
    </div>
    <button class="button" @click="openCreate">
      <FilePlus2 :size="18" />Tạo hồ sơ
    </button>
  </header>
  <section class="card">
    <div class="toolbar">
      <div class="tabs">
        <button
          v-for="tab in [
            { value: '', label: 'Tất cả' },
            { value: 'draft', label: 'Bản nháp' },
            { value: 'processing', label: 'Đang xử lý' },
            { value: 'needs_revision', label: 'Cần sửa' },
            { value: 'approved', label: 'Đã duyệt' },
          ]"
          :key="tab.value"
          class="tab"
          :class="{ active: status === tab.value }"
          @click="status = tab.value"
        >
          {{ tab.label }}
        </button>
      </div>
      <label class="search-box"
        ><Search :size="17" /><input
          v-model.lazy="search"
          type="search"
          placeholder="Tìm hồ sơ…"
          aria-label="Tìm hồ sơ"
      /></label>
    </div>
    <StatePanel
      :loading="cases.isPending.value"
      :error="cases.error.value"
      :empty="cases.data.value?.items.length === 0"
      :title="status || search ? 'Chưa có hồ sơ phù hợp' : 'Tạo hồ sơ đầu tiên'"
      :description="
        status || search
          ? 'Thử bỏ bộ lọc hoặc tìm bằng từ khác.'
          : 'Hồ sơ là đề nghị cần người có thẩm quyền duyệt: chọn mẫu, điền thông tin, đính kèm tài liệu rồi chuyển duyệt.'
      "
      @retry="cases.refetch()"
      ><button v-if="session.can('cases.create')" class="button small" @click="openCreate">
        <FilePlus2 :size="16" />Tạo hồ sơ
      </button></StatePanel
    >
    <div v-if="cases.data.value?.items.length" class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Hồ sơ</th>
            <th>Trạng thái</th>
            <th>Cập nhật</th>
            <th>Lần sửa</th>
            <th />
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in cases.data.value.items" :key="item.id">
            <td>
              <div class="primary-cell">
                <span class="file-icon"><Files :size="20" /></span>
                <div>
                  <RouterLink :to="`/cases/${item.id}`" class="row-link">{{
                    item.title
                  }}</RouterLink
                  ><small class="mono">{{ item.code }}</small>
                </div>
              </div>
            </td>
            <td><StatusBadge :status="item.status" /></td>
            <td class="muted">
              {{ formatDate(item.updated_at || item.created_at, true) }}
            </td>
            <td>
              <span class="tag">{{ item.revision > 1 ? `${item.revision - 1} lần` : 'Chưa sửa' }}</span>
            </td>
            <td>
              <RouterLink
                :to="`/cases/${item.id}`"
                class="icon-button"
                :aria-label="`Mở ${item.title}`"
                ><ArrowRight :size="17"
              /></RouterLink>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-if="cases.data.value?.has_more || cursor" class="pagination">
      <button
        class="button secondary small"
        :disabled="!cursor"
        @click="cursor = null"
      >
        Về đầu</button
      ><button
        class="button secondary small"
        :disabled="!cases.data.value?.has_more"
        @click="cursor = cases.data.value?.next_cursor ?? null"
      >
        Trang tiếp <ChevronRight :size="15" />
      </button>
    </div>
  </section>
  <ModalDialog v-if="showCreate" title="Tạo hồ sơ mới" wide @close="closeCreate"
    ><div v-if="error" class="notice error error-inline" role="alert">
      <div>
        {{ errorText(error)
        }}<code v-if="error instanceof ApiError && error.traceId">{{
          error.traceId
        }}</code>
      </div>
    </div>
    <StatePanel
      v-if="forms.isPending.value || forms.error.value"
      :loading="forms.isPending.value"
      :error="forms.error.value"
      @retry="forms.refetch()"
    />
    <div
      v-else-if="forms.data.value?.items.length === 0"
      class="notice warning"
    >
      Chưa có biểu mẫu đã phát hành. Nhờ lãnh đạo phòng hoặc ban giám đốc tạo
      mẫu trong Thiết lập trước.
    </div>
    <form v-else @submit.prevent="create">
      <div class="stack">
        <div class="form-grid">
          <div class="field full-width">
            <label for="case-title"
              >Tên hồ sơ<span class="required"> *</span></label
            ><input
              id="case-title"
              v-model="title"
              required
              maxlength="255"
              autofocus
              placeholder="Ví dụ: Đề nghị phê duyệt kế hoạch công tác"
            />
          </div>
          <div class="field full-width">
            <label for="case-form"
              >Mẫu hồ sơ<span class="required"> *</span></label
            ><select id="case-form" v-model="formId" required>
              <option value="">Chọn mẫu đã phát hành</option>
              <option
                v-for="form in forms.data.value?.items"
                :key="form.id"
                :value="form.id"
              >
                {{ form.name }}
              </option></select
            ><small v-if="selectedForm?.description">{{
              selectedForm.description
            }}</small>
          </div>
          <div v-if="matchingPackages.length" class="field full-width">
            <label for="case-package">Gói quy trình đã phát hành</label>
            <select id="case-package" v-model="packageVersionId" required>
              <option v-for="item in matchingPackages" :key="item.id" :value="item.id">
                {{ item.package_name }} · phiên bản {{ item.version_no }}
              </option>
            </select>
          </div>
        </div>
        <div class="form-grid">
          <div class="field">
            <label for="case-priority">Mức độ</label
            ><select id="case-priority" v-model="priority">
              <option value="low">Thấp</option>
              <option value="normal">Bình thường</option>
              <option value="high">Cao</option>
              <option value="urgent">Khẩn</option>
            </select>
          </div>
          <div class="field">
            <label for="case-due">Hạn xử lý</label
            ><input id="case-due" v-model="dueAt" type="datetime-local" />
          </div>
          <div class="field">
            <label for="case-assignee">Người phụ trách</label
            ><select id="case-assignee" v-model="assigneeId">
              <option value="">Tôi (người tạo)</option>
              <option
                v-for="member in members.data.value?.items"
                :key="member.id"
                :value="member.id"
              >
                {{ member.display_name }}
              </option></select
            ><small>Người nhận phải thuộc phạm vi đơn vị của hồ sơ.</small>
          </div>
        </div>
        <template v-if="selectedForm"
          ><hr class="divider" style="margin: 0" />
          <div>
            <span class="eyebrow">THÔNG TIN HỒ SƠ</span
            ><SchemaForm
              v-model="payload"
              :fields="selectedForm.fields"
              :errors="errors"
              :disabled="busy"
            />
          </div>
          <div>
            <span class="eyebrow">TÀI LIỆU ĐÍNH KÈM</span>
            <p
              v-if="!files.data.value?.items.length"
              class="muted"
              style="font-size: 14px"
            >
              Chưa có tài liệu. Bạn có thể bổ sung sau từ kho Tài liệu.
            </p>
            <div class="case-document-list">
              <label
                v-for="file in files.data.value?.items"
                :key="file.id"
                class="case-selection"
                ><input
                  v-model="fileIds"
                  type="checkbox"
                  :value="file.id"
                /><span>{{ file.name }}</span></label
              >
            </div>
          </div>
          <div class="notice">
            <Files :size="19" /><span
              >Hồ sơ được lưu dưới dạng <strong>bản nháp</strong>. Bạn có thể
              kiểm tra lại trước khi chuyển duyệt.</span
            >
          </div></template
        >
      </div>
      <div class="form-actions">
        <button
          class="button secondary"
          type="button"
          :disabled="busy"
          @click="closeCreate"
        >
          Hủy</button
        ><button class="button" :disabled="busy || !selectedForm">
          {{ busy ? 'Đang tạo…' : 'Tạo bản nháp' }}
        </button>
      </div>
    </form></ModalDialog
  >
</template>
