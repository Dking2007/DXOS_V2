<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import {
  ArrowRight,
  ChevronRight,
  CalendarClock,
  FilePlus2,
  Files,
  Flame,
  Grid2X2,
  List,
  Paperclip,
  Pencil,
  Search,
  Send,
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
import type { CaseItem, DriveFile, FormTemplate } from '@dx/web-shared/types.ts'
import type { components } from '@dx/web-shared/generated/workspace-api.ts'
import { initialPayload, validatePayload } from '@dx/web-shared/forms.ts'
import StatePanel from '@dx/web-shared/components/StatePanel.vue'
import ModalDialog from '@dx/web-shared/components/ModalDialog.vue'
import { toast } from '../ui/toast'
import { useSession } from '../stores/session'
import { confirmDiscard } from '../ui/unsaved'
import StatusBadge from '@dx/web-shared/components/StatusBadge.vue'
import SchemaForm from '@dx/web-shared/components/SchemaForm.vue'
import { initialsOf } from '../ui/people'
import { caseTone } from '../ui/caseFolder'
const route = useRoute()
const session = useSession()
/** One's own draft or returned dossier: offer to continue it or submit it straight from the list. */
function isMyDraft(item: CaseItem) {
  return ['draft', 'needs_revision'].includes(item.status) && item.owner_id === session.user?.id
}
const router = useRouter()
const queryClient = useQueryClient()
// Archived dossiers are a separate pile rather than a status: they keep their result.
const ARCHIVED = 'archived'
const status = ref('')
// Folders by default; a person's own choice of folders or table is remembered on this browser.
function storedView(): 'folders' | 'table' {
  try {
    return window.localStorage.getItem('dx-cases-view') === 'table' ? 'table' : 'folders'
  } catch {
    return 'folders'
  }
}
const view = ref<'folders' | 'table'>(storedView())
watch(view, (mode) => {
  try {
    window.localStorage.setItem('dx-cases-view', mode)
  } catch {
    // Storage blocked: the choice lasts for this visit only.
  }
})
const isPast = (value: string | null | undefined) => !!value && new Date(value) < new Date()
const search = ref('')
const cursor = ref<string | null>(null)
const cases = useQuery({
  queryKey: computed(() => ['cases', status.value, search.value, cursor.value]),
  queryFn: () =>
    api.request<Page<CaseItem>>(
      `/cases${queryString(
        status.value === ARCHIVED
          ? { archived: true, q: search.value, cursor: cursor.value }
          : { status: status.value, q: search.value, cursor: cursor.value },
      )}`,
    ),
})
const forms = useQuery({
  queryKey: ['forms'],
  queryFn: () => api.request<Page<FormTemplate>>('/forms'),
})
interface AvailableProcess {
  id: string
  name: string
  description: string
  version_no: number
  form_id: string
  form_name: string
  required_file_count: number
}
const processes = useQuery({
  queryKey: ['processes', 'available'],
  queryFn: () => api.request<Page<AvailableProcess>>('/processes/available'),
})
const files = useQuery({
  queryKey: ['drive', 'case-picker'],
  queryFn: () => api.request<Page<DriveFile>>('/drive/files'),
})
const showCreate = ref(false)
const title = ref('')
const formId = ref('')
const processId = ref('')
const payload = ref<Record<string, unknown>>({})
const fileIds = ref<string[]>([])
const priority = ref<'low' | 'normal' | 'high' | 'urgent'>('normal')
const errors = ref<Record<string, string>>({})
const error = ref<unknown>(null)
const busy = ref(false)
const intent = ref(newIntent())
const selectedForm = computed(() =>
  forms.data.value?.items.find((form) => form.id === formId.value),
)
const selectedProcess = computed(() => processes.data.value?.items.find((item) => item.id === processId.value))
// People start from a process they may use; a form with none of its own still works by its steps.
const standaloneForms = computed(() => {
  const covered = new Set(processes.data.value?.items.map((item) => item.form_id))
  return forms.data.value?.items.filter((form) => !covered.has(form.id)) ?? []
})
const choice = computed({
  get: () => (processId.value ? `process:${processId.value}` : formId.value ? `form:${formId.value}` : ''),
  set: (value: string) => {
    const [kind, id] = value.split(':') as [string, string | undefined]
    processId.value = kind === 'process' ? (id ?? '') : ''
    formId.value =
      kind === 'process' ? (processes.data.value?.items.find((item) => item.id === id)?.form_id ?? '') : (id ?? '')
  },
})
watch(formId, () => {
  payload.value = initialPayload(selectedForm.value?.fields ?? [])
  errors.value = {}
})
watch([status, search], () => {
  cursor.value = null
})
const canCreate = computed(() => session.can('cases.create'))
function clearFilters() {
  status.value = ''
  search.value = ''
}
function openCreate() {
  if (!canCreate.value) return
  // A dialog closed with "discard" starts empty next time.
  title.value = ''
  processId.value = ''
  formId.value = ''
  fileIds.value = []
  errors.value = {}
  showCreate.value = true
  error.value = null
  intent.value = newIntent()
  priority.value = 'normal'
}
const createDirty = computed(
  () =>
    !!title.value.trim() ||
    !!formId.value ||
    priority.value !== 'normal' ||
    fileIds.value.length > 0 ||
    JSON.stringify(payload.value) !== JSON.stringify(initialPayload(selectedForm.value?.fields ?? [])),
)
const createBlocked = computed(() =>
  !title.value.trim() ? 'Nhập tên hồ sơ trước.' : !selectedForm.value ? 'Chọn quy trình trước.' : '',
)
async function closeCreate() {
  if (!busy.value && await confirmDiscard(createDirty.value)) {
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
async function create() {
  if (busy.value || createBlocked.value || !selectedForm.value) return
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
        process_id: processId.value || null,
        payload: payload.value,
        file_ids: fileIds.value,
        priority: priority.value,
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
  <header class="page-head compact">
    <h1 class="sr-only">Hồ sơ</h1>
    <button v-if="canCreate" class="button" @click="openCreate">
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
            { value: 'cancelled', label: 'Đã hủy' },
            { value: ARCHIVED, label: 'Lưu trữ' },
          ]"
          :key="tab.value"
          class="tab"
          :class="{ active: status === tab.value }"
          @click="status = tab.value"
        >
          {{ tab.label }}
        </button>
      </div>
      <div class="toolbar-end">
        <label class="search-box"
          ><Search :size="17" /><input
            v-model.lazy="search"
            type="search"
            placeholder="Tìm hồ sơ…"
            aria-label="Tìm hồ sơ"
        /></label>
        <div class="view-switch" role="group" aria-label="Cách xem">
          <button
            type="button"
            :class="{ active: view === 'folders' }"
            :aria-pressed="view === 'folders'"
            aria-label="Xem dạng tập hồ sơ"
            title="Xem dạng tập hồ sơ"
            @click="view = 'folders'"
          >
            <Grid2X2 :size="17" /></button
          ><button
            type="button"
            :class="{ active: view === 'table' }"
            :aria-pressed="view === 'table'"
            aria-label="Xem dạng bảng"
            title="Xem dạng bảng"
            @click="view = 'table'"
          >
            <List :size="17" />
          </button>
        </div>
      </div>
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
      ><button v-if="status || search" class="button small secondary" @click="clearFilters">
        Xóa bộ lọc</button
      ><button v-else-if="canCreate" class="button small" @click="openCreate">
        <FilePlus2 :size="16" />Tạo hồ sơ
      </button></StatePanel
    >
    <ul v-if="view === 'folders' && cases.data.value?.items.length" class="folders">
      <li
        v-for="item in cases.data.value.items"
        :key="item.id"
        class="folder"
        :class="[`tone-${caseTone(item.status, item.archived_at)}`, { overdue: item.overdue }]"
      >
        <span class="folder-tab mono">{{ item.code }}</span>
        <div class="folder-body">
          <div class="folder-top">
            <span class="folder-form" :title="item.form_name">{{ item.form_name || 'Hồ sơ' }}</span>
            <span v-if="item.priority === 'urgent' || item.priority === 'high'" class="folder-flag" :class="item.priority"
              ><Flame :size="13" />{{ item.priority === 'urgent' ? 'Khẩn' : 'Cao' }}</span
            >
          </div>
          <RouterLink :to="`/cases/${item.id}`" class="folder-title" :title="item.title">{{ item.title }}</RouterLink>
          <div class="folder-status">
            <StatusBadge :status="item.status" /><span v-if="item.overdue" class="folder-overdue">Quá hạn</span>
          </div>
          <div class="folder-waiting">
            <template v-if="item.waiting_on?.length">
              <small class="muted">Đang chờ</small>
              <span class="folder-who"
                ><strong>{{ item.waiting_on[0]!.name || 'Chưa có người nhận' }}</strong>
                <small
                  >{{ item.waiting_on[0]!.label
                  }}<template v-if="item.waiting_on[0]!.due_at">
                    ·
                    <span :class="{ 'overdue-text': isPast(item.waiting_on[0]!.due_at) }"
                      >hạn {{ formatDate(item.waiting_on[0]!.due_at) }}</span
                    ></template
                  ><template v-if="item.waiting_on.length > 1"> · +{{ item.waiting_on.length - 1 }}</template></small
                ></span
              >
            </template>
            <div v-else-if="isMyDraft(item)" class="row-actions folder-actions">
              <RouterLink :to="`/cases/${item.id}?action=edit`" class="button secondary small"
                ><Pencil :size="14" />Tiếp tục soạn</RouterLink
              ><RouterLink :to="`/cases/${item.id}?action=submit`" class="button small"
                ><Send :size="14" />Trình</RouterLink
              >
            </div>
            <small v-else-if="item.status === 'pending_workflow_start'" class="muted">Đang chuyển duyệt…</small>
            <small v-else-if="item.due_at" class="muted folder-due"
              ><CalendarClock :size="13" />Hạn {{ formatDate(item.due_at) }}</small
            >
          </div>
          <footer class="folder-foot">
            <span class="folder-owner" :title="item.owner_name"
              ><span class="folder-avatar" aria-hidden="true">{{ initialsOf(item.owner_name) }}</span
              >{{ item.owner_name || '—' }}</span
            >
            <span v-if="item.file_ids?.length" class="folder-meta" :title="`${item.file_ids.length} tài liệu`"
              ><Paperclip :size="13" />{{ item.file_ids.length }}</span
            >
            <span class="folder-meta">{{ formatDate(item.updated_at || item.created_at) }}</span>
          </footer>
        </div>
      </li>
    </ul>
    <div v-else-if="cases.data.value?.items.length" class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Hồ sơ</th>
            <th>Trạng thái</th>
            <th>Đang chờ</th>
            <th>Cập nhật</th>
            <th />
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in cases.data.value.items" :key="item.id">
            <td>
              <div class="primary-cell">
                <span class="file-icon"><Files :size="20" /></span>
                <div>
                  <RouterLink :to="`/cases/${item.id}`" class="row-link case-title" :title="item.title">{{
                    item.title
                  }}</RouterLink
                  ><small class="mono">{{ item.code }}</small>
                </div>
              </div>
            </td>
            <td><StatusBadge :status="item.status" /></td>
            <td class="waiting-cell">
              <template v-if="item.waiting_on?.length">
                <div v-for="(who, index) in item.waiting_on.slice(0, 2)" :key="index">
                  <strong>{{ who.name || 'Chưa có người nhận' }}</strong>
                  <small
                    >{{ who.label
                    }}<template v-if="who.due_at">
                      ·
                      <span :class="{ 'overdue-text': new Date(who.due_at) < new Date() }"
                        >hạn {{ formatDate(who.due_at) }}</span
                      ></template
                    ></small
                  >
                </div>
                <small v-if="item.waiting_on.length > 2" class="muted"
                  >và {{ item.waiting_on.length - 2 }} người khác</small
                >
              </template>
              <div v-else-if="isMyDraft(item)" class="row-actions">
                <RouterLink :to="`/cases/${item.id}?action=edit`" class="button secondary small"
                  ><Pencil :size="14" />Tiếp tục soạn</RouterLink
                ><RouterLink :to="`/cases/${item.id}?action=submit`" class="button small"
                  ><Send :size="14" />Trình</RouterLink
                >
              </div>
              <span v-else-if="item.status === 'pending_workflow_start'" class="muted">Đang chuyển duyệt…</span>
              <span v-else class="muted">—</span>
            </td>
            <td class="muted nowrap">
              {{ formatDate(item.updated_at || item.created_at, true) }}
            </td>
            <td>
              <RouterLink
                :to="`/cases/${item.id}`"
                class="icon-button"
                :aria-label="`Mở ${item.title}`"
                title="Mở hồ sơ"
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
              >Quy trình<span class="required"> *</span></label
            ><select id="case-form" v-model="choice" required>
              <option value="">Chọn quy trình</option>
              <optgroup v-if="processes.data.value?.items.length" label="Quy trình nghiệp vụ">
                <option v-for="item in processes.data.value.items" :key="item.id" :value="`process:${item.id}`">
                  {{ item.name }}
                </option>
              </optgroup>
              <optgroup v-if="standaloneForms.length" label="Biểu mẫu chưa có quy trình">
                <option v-for="form in standaloneForms" :key="form.id" :value="`form:${form.id}`">{{ form.name }}</option>
              </optgroup></select
            ><small v-if="selectedProcess"
              >{{ selectedProcess.description || selectedForm?.description }} Biểu mẫu “{{ selectedProcess.form_name }}”,
              phiên bản {{ selectedProcess.version_no
              }}<template v-if="selectedProcess.required_file_count">
                · cần ít nhất {{ selectedProcess.required_file_count }} tài liệu</template
              >.</small
            ><small v-else-if="selectedForm?.description">{{ selectedForm.description }}</small>
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
        </div>
        <template v-if="selectedForm"
          ><hr class="divider case-divider" />
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
            <p v-if="!files.data.value?.items.length" class="muted">
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
                  :disabled="busy"
                /><span class="case-file-name" :title="file.name">{{ file.name }}</span></label
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
        ><button class="button" :disabled="busy || !!createBlocked" :title="createBlocked">
          {{ busy ? 'Đang tạo…' : 'Tạo bản nháp' }}
        </button>
      </div>
    </form></ModalDialog
  >
</template>
<style scoped>
.toolbar-end {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}
.view-switch {
  display: inline-flex;
  padding: 3px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--surface-2);
}
.view-switch button {
  display: grid;
  place-items: center;
  width: 34px;
  height: 30px;
  border: 0;
  border-radius: 7px;
  background: none;
  color: var(--muted);
  cursor: pointer;
}
.view-switch button.active {
  background: var(--surface);
  color: var(--teal-ink);
  box-shadow: 0 1px 3px rgb(15 23 42 / 12%);
}
.view-switch button:focus-visible {
  outline: none;
  box-shadow: var(--focus-ring);
}
/* Each dossier is a folder: a tab with its number, a cover tinted by where it stands, and the
   edge of the papers inside showing underneath. */
.folders {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(270px, 1fr));
  gap: 30px 20px;
  margin: 0;
  padding: 30px var(--space-5) var(--space-6);
  list-style: none;
}
.folder {
  --tone-ink: var(--muted);
  --tone-soft: var(--surface-3);
  --tone-line: var(--border);
  position: relative;
  display: flex;
  min-width: 0;
}
.tone-moving {
  --tone-ink: var(--teal-ink);
  --tone-soft: var(--teal-soft);
  --tone-line: var(--teal-line);
}
.tone-attention {
  --tone-ink: var(--amber-ink);
  --tone-soft: var(--amber-soft);
  --tone-line: var(--amber-line);
}
.tone-done {
  --tone-ink: var(--green-ink);
  --tone-soft: var(--green-soft);
  --tone-line: var(--green-line);
}
.tone-stopped {
  --tone-ink: var(--red-ink);
  --tone-soft: var(--red-soft);
  --tone-line: var(--red-line);
}
.folder-tab {
  position: absolute;
  top: -19px;
  left: 0;
  z-index: 1;
  max-width: 60%;
  height: 20px;
  padding: 2px 14px 0 12px;
  border: 1px solid var(--tone-line);
  border-bottom: 0;
  border-radius: 9px 14px 0 0;
  background: var(--tone-line);
  color: var(--tone-ink);
  font-size: 0.75rem;
  font-weight: 600;
  line-height: 17px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.folder-body {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
  min-width: 0;
  padding: 16px 16px 12px;
  border: 1px solid var(--tone-line);
  border-top: 4px solid var(--tone-line);
  border-radius: 0 14px 14px 14px;
  background: linear-gradient(180deg, var(--tone-soft), var(--surface) 64px);
  /* Two sheets peeking out below the cover. */
  box-shadow:
    0 4px 0 -1px var(--surface),
    0 4px 0 0 var(--border),
    0 8px 0 -2px var(--surface),
    0 8px 0 -1px var(--border);
  transition:
    transform 0.16s,
    box-shadow 0.16s;
}
.folder:hover .folder-body,
.folder:focus-within .folder-body {
  transform: translateY(-3px);
  box-shadow:
    0 4px 0 -1px var(--surface),
    0 4px 0 0 var(--border),
    0 8px 0 -2px var(--surface),
    0 8px 0 -1px var(--border),
    0 16px 30px -12px rgb(15 23 42 / 28%);
}
.folder:hover .folder-tab,
.folder:focus-within .folder-tab {
  transform: translateY(-3px);
  transition: transform 0.16s;
}
.folder-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-height: 20px;
}
.folder-form {
  min-width: 0;
  overflow: hidden;
  color: var(--tone-ink);
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.02em;
  text-overflow: ellipsis;
  text-transform: uppercase;
  white-space: nowrap;
}
.folder-flag {
  display: inline-flex;
  flex-shrink: 0;
  align-items: center;
  gap: 3px;
  padding: 1px 8px;
  border-radius: 999px;
  background: var(--amber-soft);
  color: var(--amber-ink);
  font-size: 0.75rem;
  font-weight: 600;
}
.folder-flag.urgent {
  background: var(--red-soft);
  color: var(--red-ink);
}
.folder-title {
  display: -webkit-box;
  min-height: 2.6em;
  overflow: hidden;
  color: var(--navy);
  font-size: 1rem;
  font-weight: 650;
  line-height: 1.3;
  text-decoration: none;
  overflow-wrap: anywhere;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
}
/* The whole folder opens the dossier; its own buttons sit above this. */
.folder-title::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
}
.folder-title:focus-visible {
  outline: none;
}
.folder:has(.folder-title:focus-visible) .folder-body {
  box-shadow: var(--focus-ring);
}
.folder-status {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}
.folder-overdue {
  padding: 1px 8px;
  border-radius: 999px;
  background: var(--red-soft);
  color: var(--red-ink);
  font-size: 0.75rem;
  font-weight: 600;
}
.folder-waiting {
  display: grid;
  gap: 2px;
  min-height: 40px;
  align-content: start;
}
.folder-who {
  display: grid;
  min-width: 0;
}
.folder-who strong {
  overflow: hidden;
  font-size: 0.875rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.folder-who small {
  color: var(--muted);
  font-size: 0.75rem;
}
.folder-actions {
  position: relative;
  z-index: 1;
}
.folder-due {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.folder-foot {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: auto;
  padding-top: 10px;
  border-top: 1px dashed var(--border);
  color: var(--muted);
  font-size: 0.75rem;
}
.folder-owner {
  display: inline-flex;
  flex: 1;
  align-items: center;
  gap: 6px;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.folder-avatar {
  display: grid;
  flex-shrink: 0;
  place-items: center;
  width: 22px;
  height: 22px;
  border-radius: 7px;
  background: var(--surface-3);
  color: var(--navy);
  font-size: 0.625rem;
  font-weight: 700;
}
.folder-meta {
  display: inline-flex;
  flex-shrink: 0;
  align-items: center;
  gap: 3px;
  white-space: nowrap;
}
@media (max-width: 640px) {
  .folders {
    grid-template-columns: 1fr;
    padding-inline: var(--space-4);
  }
  .toolbar-end {
    width: 100%;
  }
  .folder-waiting {
    min-height: 0;
  }
  .folder-waiting:empty {
    display: none;
  }
  .folder-title {
    min-height: 0;
  }
  .toolbar-end .search-box {
    flex: 1;
  }
}
@media (prefers-reduced-motion: reduce) {
  .folder-body,
  .folder-tab {
    transition: none !important;
  }
  .folder:hover .folder-body,
  .folder:hover .folder-tab {
    transform: none;
  }
}
.case-title {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  overflow-wrap: anywhere;
}
.nowrap {
  white-space: nowrap;
}
.case-divider {
  margin: 0;
}
.case-file-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
