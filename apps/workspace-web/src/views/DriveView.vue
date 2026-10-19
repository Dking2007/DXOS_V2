<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import {
  ChevronRight,
  Copy,
  Download,
  File,
  FilePlus2,
  FileText,
  FolderClosed,
  FolderPlus,
  History,
  Pencil,
  Search,
  Share2,
  Tags,
  Trash2,
  Upload,
  X,
} from 'lucide-vue-next'
import { api } from '../api'
import {
  ApiError,
  errorText,
  formatDate,
  formatSize,
  newIntent,
  queryString,
} from '@dx/web-shared/api.ts'
import type { Page } from '@dx/web-shared/api.ts'
import {
  copySummary,
  folderGrantsPending,
  labelsToText,
  parseLabels,
  shareLabel as sharedShareLabel,
} from '@dx/web-shared/drive.ts'
import type {
  DriveFile,
  FileVersion,
  Folder,
  Share,
  User,
} from '@dx/web-shared/types.ts'
import StatePanel from '@dx/web-shared/components/StatePanel.vue'
import ModalDialog from '@dx/web-shared/components/ModalDialog.vue'
const queryClient = useQueryClient()
const folder = ref<string | null>(null)
const crumbs = ref<Folder[]>([])
const search = ref('')
const searchQuery = ref('')
let timer: ReturnType<typeof setTimeout> | undefined
watch(search, (value) => {
  clearTimeout(timer)
  timer = setTimeout(() => {
    searchQuery.value = value
    cursor.value = null
  }, 250)
})
onBeforeUnmount(() => clearTimeout(timer))
const trash = ref(false)
const cursor = ref<string | null>(null)
const files = useQuery({
  queryKey: computed(() => [
    'drive',
    folder.value,
    searchQuery.value,
    trash.value,
    cursor.value,
  ]),
  queryFn: () =>
    api.request<Page<DriveFile>>(
      `/drive/files${queryString({ folder_id: folder.value, q: searchQuery.value, trash: trash.value, cursor: cursor.value })}`,
    ),
})
const folders = useQuery({
  queryKey: computed(() => ['folders', folder.value]),
  queryFn: () =>
    api.request<Page<Folder>>(
      `/drive/folders${queryString({ parent_id: folder.value })}`,
    ),
})
const users = useQuery({
  queryKey: ['users'],
  queryFn: () => api.request<Page<User>>('/users'),
})
const selected = ref<DriveFile | null>(null)
const selectedFolder = ref<Folder | null>(null)
const modal = ref<
  | 'upload'
  | 'folder'
  | 'document'
  | 'rename'
  | 'labels'
  | 'copy'
  | 'share'
  | 'versions'
  | 'trash'
  | 'folder-rename'
  | 'folder-share'
  | null
>(null)
const name = ref('')
const kind = ref('docx')
const targetFolder = ref<string>('')
const labelText = ref('')
const userId = ref('')
const access = ref('read')
const uploadFile = ref<File | null>(null)
const progress = ref<number | null>(null)
const busy = ref(false)
const error = ref<unknown>(null)
const versionQuery = useQuery({
  queryKey: computed(() => ['versions', selected.value?.id]),
  queryFn: () =>
    api.request<Page<FileVersion>>(
      `/drive/files/${selected.value!.id}/versions`,
    ),
  enabled: computed(() => modal.value === 'versions' && !!selected.value),
})
const folderShares = useQuery({
  queryKey: computed(() => ['folder-shares', selectedFolder.value?.id]),
  queryFn: () =>
    api.request<Page<Share>>(
      `/drive/folders/${selectedFolder.value!.id}/shares`,
    ),
  enabled: computed(
    () => modal.value === 'folder-share' && !!selectedFolder.value,
  ),
})
const anyFolderSyncing = computed(() =>
  (folders.data.value?.items ?? []).some((item) =>
    folderGrantsPending(item),
  ),
)
/** The document a copy would duplicate, carrying the labels it would end up with. */
const copyPreview = computed(() => {
  if (!selected.value) return null
  const typed = labelText.value.trim()
  return {
    name: selected.value.name,
    labels: typed ? parseLabels(labelText.value) : selected.value.labels,
  }
})
function shareLabel(share: Share) {
  return sharedShareLabel(share, users.data.value?.items ?? [])
}
function open(type: typeof modal.value, item?: DriveFile) {
  modal.value = type
  selected.value = item ?? null
  selectedFolder.value = null
  name.value = item?.name ?? ''
  targetFolder.value = item?.folder_id ?? ''
  labelText.value = labelsToText(item?.labels)
  error.value = null
  progress.value = null
  uploadFile.value = null
}
function openFolder(type: 'folder-rename' | 'folder-share', item: Folder) {
  modal.value = type
  selected.value = null
  selectedFolder.value = item
  name.value = item.name
  targetFolder.value = item.parent_id ?? ''
  error.value = null
  progress.value = null
  uploadFile.value = null
}
function close() {
  if (!busy.value) modal.value = null
}
function enter(item: Folder) {
  folder.value = item.id
  crumbs.value.push(item)
  cursor.value = null
}
function go(index: number) {
  crumbs.value = crumbs.value.slice(0, index + 1)
  folder.value = index < 0 ? null : crumbs.value[index]!.id
  cursor.value = null
}
async function refresh() {
  await queryClient.invalidateQueries({ queryKey: ['drive'] })
  await queryClient.invalidateQueries({ queryKey: ['folders'] })
  await queryClient.invalidateQueries({ queryKey: ['versions'] })
}
async function perform(operation: () => Promise<unknown>, keep = false) {
  busy.value = true
  error.value = null
  try {
    await operation()
    await refresh()
    if (!keep) modal.value = null
  } catch (cause) {
    error.value = cause
  } finally {
    busy.value = false
  }
}
async function save() {
  if (modal.value === 'folder')
    return perform(() =>
      api.request('/drive/folders', {
        method: 'POST',
        body: JSON.stringify({ name: name.value, parent_id: folder.value }),
      }),
    )
  if (modal.value === 'document')
    return perform(() =>
      api.request('/drive/files/create-document', {
        method: 'POST',
        headers: { 'Idempotency-Key': newIntent() },
        body: JSON.stringify({
          name: name.value,
          kind: kind.value,
          folder_id: folder.value,
        }),
      }),
    )
  if (modal.value === 'rename' && selected.value)
    return perform(() =>
      api.request(`/drive/files/${selected.value!.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          expected_revision: selected.value!.revision,
          name: name.value,
          folder_id: targetFolder.value || null,
        }),
      }),
    )
  if (modal.value === 'labels' && selected.value)
    return perform(() =>
      api.request(`/drive/files/${selected.value!.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          expected_revision: selected.value!.revision,
          labels: parseLabels(labelText.value),
        }),
      }),
    )
  if (modal.value === 'copy' && selected.value)
    return perform(() =>
      api.request(`/drive/files/${selected.value!.id}/copy`, {
        method: 'POST',
        headers: { 'Idempotency-Key': newIntent() },
        body: JSON.stringify({
          name: name.value || null,
          folder_id: targetFolder.value || null,
          labels: labelText.value.trim() ? parseLabels(labelText.value) : null,
        }),
      }),
    )
  if (modal.value === 'share' && selected.value)
    return perform(() =>
      api.request(`/drive/files/${selected.value!.id}/shares`, {
        method: 'PUT',
        body: JSON.stringify({
          expected_revision: selected.value!.revision,
          user_id: userId.value,
          access: access.value,
        }),
      }),
    )
  if (modal.value === 'folder-rename' && selectedFolder.value)
    return perform(() =>
      api.request(`/drive/folders/${selectedFolder.value!.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          expected_revision: selectedFolder.value!.revision ?? 1,
          name: name.value,
          parent_id: targetFolder.value || null,
        }),
      }),
    )
  if (modal.value === 'folder-share' && selectedFolder.value)
    return perform(() =>
      api.request(`/drive/folders/${selectedFolder.value!.id}/shares`, {
        method: 'PUT',
        body: JSON.stringify({
          expected_revision: selectedFolder.value!.revision ?? 1,
          user_id: userId.value,
          access: access.value,
        }),
      }),
    )
  if (modal.value === 'trash' && selected.value)
    return perform(() =>
      api.request(`/drive/files/${selected.value!.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          expected_revision: selected.value!.revision,
          trashed: !trash.value,
        }),
      }),
    )
  if (modal.value === 'upload' && uploadFile.value) {
    progress.value = 0
    const data = new FormData()
    data.append('file', uploadFile.value)
    if (folder.value) data.append('folder_id', folder.value)
    await perform(async () => {
      // Fetch does not expose upload progress; show indeterminate finalization rather than a false percentage.
      progress.value = null
      await api.request('/drive/files', {
        method: 'POST',
        body: data,
        headers: { 'Idempotency-Key': newIntent() },
      })
    })
  }
}
async function download(item: DriveFile) {
  error.value = null
  try {
    const result = await api.request<{ url: string }>(
      `/drive/files/${item.id}/download`,
      { method: 'POST' },
    )
    window.location.assign(result.url)
  } catch (cause) {
    error.value = cause
  }
}
async function restore(version: FileVersion) {
  if (!selected.value) return
  await perform(() =>
    api.request(`/drive/files/${selected.value!.id}/restore`, {
      method: 'POST',
      headers: { 'Idempotency-Key': newIntent() },
      body: JSON.stringify({
        version_id: version.id,
        expected_revision: selected.value!.revision,
      }),
    }),
  )
}
function pickFile(event: Event) {
  uploadFile.value = (event.target as HTMLInputElement).files?.[0] ?? null
}
</script>
<template>
  <header class="page-head">
    <div>
      <span class="eyebrow">KHO TÀI LIỆU</span>
      <h1>Tài liệu của bạn</h1>
      <p>Lưu trữ, cộng tác và giữ đúng từng phiên bản.</p>
    </div>
    <div class="page-actions">
      <button class="button secondary" @click="open('folder')">
        <FolderPlus :size="17" />Tạo thư mục</button
      ><button class="button secondary" @click="open('document')">
        <FilePlus2 :size="17" />Tạo tài liệu</button
      ><button class="button" @click="open('upload')">
        <Upload :size="17" />Tải tệp lên
      </button>
    </div>
  </header>
  <div v-if="error && !modal" class="notice error error-inline" role="alert">
    {{ errorText(error) }}
  </div>
  <section class="card">
    <div class="toolbar">
      <div class="tabs">
        <button
          class="tab"
          :class="{ active: !trash }"
          @click="
            () => {
              trash = false
              cursor = null
            }
          "
        >
          Tài liệu</button
        ><button
          class="tab"
          :class="{ active: trash }"
          @click="
            () => {
              trash = true
              cursor = null
            }
          "
        >
          <Trash2
            :size="13"
            style="vertical-align: middle; margin-right: 5px"
          />Thùng rác
        </button>
      </div>
      <label class="search-box"
        ><Search :size="17" /><span class="sr-only">Tìm tài liệu</span
        ><input
          v-model="search"
          placeholder="Tìm theo tên tài liệu…"
          type="search"
      /></label>
      <p v-if="anyFolderSyncing" class="notice" role="status">
        Đang cấp lại quyền cho tài liệu sau thay đổi chia sẻ hoặc di chuyển thư
        mục. Tài liệu có thể tạm thời chưa mở được.
      </p>
    </div>
    <div v-if="!trash" class="drive-location">
      <button @click="go(-1)">
        <FolderClosed
          :size="14"
          style="vertical-align: middle; margin-right: 6px"
        />Tài liệu</button
      ><template v-for="(crumb, index) in crumbs" :key="crumb.id"
        ><ChevronRight :size="13" /><button @click="go(index)">
          {{ crumb.name }}
        </button></template
      >
    </div>
    <div
      v-if="!trash && !searchQuery && folders.data.value?.items.length"
      class="folder-grid"
    >
      <div
        v-for="item in folders.data.value.items"
        :key="item.id"
        class="folder-card"
      >
        <button class="folder-open" @click="enter(item)">
          <FolderClosed :size="23" /><span>{{ item.name }}</span
          ><ChevronRight
            :size="14"
            style="margin-left: auto; color: var(--muted); fill: none"
          />
        </button>
        <div class="folder-tools">
          <button
            class="icon-button"
            :aria-label="`Đổi tên hoặc di chuyển ${item.name}`"
            @click="openFolder('folder-rename', item)"
          >
            <Pencil :size="15" /></button
          ><button
            class="icon-button"
            :aria-label="`Chia sẻ quyền kế thừa cho ${item.name}`"
            @click="openFolder('folder-share', item)"
          >
            <Share2 :size="15" />
          </button>
        </div>
      </div>
    </div>
    <StatePanel
      :loading="files.isPending.value"
      :error="files.error.value"
      :empty="files.data.value?.items.length === 0"
      :title="
        trash
          ? 'Thùng rác đang trống'
          : searchQuery
            ? 'Không tìm thấy tài liệu'
            : 'Chưa có tài liệu trong thư mục này'
      "
      :description="
        trash
          ? 'Tệp đã đưa vào thùng rác có thể khôi phục tại đây.'
          : searchQuery
            ? 'Thử tìm bằng một từ khóa khác.'
            : 'Tải lên tài liệu đầu tiên hoặc tạo một văn bản mới.'
      "
      @retry="files.refetch()"
    />
    <div v-if="files.data.value?.items.length" class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Tên tài liệu</th>
            <th>Chỉnh sửa gần nhất</th>
            <th>Dung lượng</th>
            <th><span class="sr-only">Thao tác</span></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in files.data.value.items" :key="item.id">
            <td>
              <div class="primary-cell">
                <span class="file-icon"><FileText :size="19" /></span>
                <div>
                  <RouterLink
                    v-if="
                      !trash &&
                      /\.(docx|xlsx|pptx|doc|xls|ppt|odt|ods|odp)$/i.test(
                        item.name,
                      )
                    "
                    class="row-link"
                    :to="`/drive/${item.id}/edit`"
                    >{{ item.name }}</RouterLink
                  ><strong v-else>{{ item.name }}</strong
                  ><small class="mono"
                    >{{ item.id.slice(0, 8) }} · bản sửa
                    {{ item.revision }}</small
                  >
                  <ul v-if="item.labels?.length" class="label-chips">
                    <li v-for="label in item.labels" :key="label">
                      {{ label }}
                    </li>
                  </ul>
                </div>
              </div>
            </td>
            <td class="muted">
              {{ formatDate(item.updated_at || item.created_at, true) }}
            </td>
            <td class="muted">{{ formatSize(item.size ?? 0) }}</td>
            <td>
              <div
                class="inline-actions"
                style="justify-content: flex-end; flex-wrap: nowrap"
              >
                <template v-if="!trash"
                  ><button
                    class="icon-button"
                    :aria-label="`Tải ${item.name}`"
                    @click="download(item)"
                  >
                    <Download :size="16" /></button
                  ><button
                    class="icon-button"
                    :aria-label="`Chia sẻ ${item.name}`"
                    @click="open('share', item)"
                  >
                    <Share2 :size="16" /></button
                  ><button
                    class="icon-button"
                    :aria-label="`Nhãn của ${item.name}`"
                    @click="open('labels', item)"
                  >
                    <Tags :size="16" /></button
                  ><button
                    class="icon-button"
                    :aria-label="`Tạo bản sao của ${item.name}`"
                    @click="open('copy', item)"
                  >
                    <Copy :size="16" /></button
                  ><button
                    class="icon-button"
                    :aria-label="`Phiên bản ${item.name}`"
                    @click="open('versions', item)"
                  >
                    <History :size="16" /></button
                  ><button
                    class="icon-button"
                    :aria-label="`Đổi tên hoặc di chuyển ${item.name}`"
                    @click="open('rename', item)"
                  >
                    <Pencil :size="15" /></button></template
                ><button
                  class="icon-button"
                  :aria-label="
                    trash
                      ? `Khôi phục ${item.name}`
                      : `Đưa ${item.name} vào thùng rác`
                  "
                  @click="open('trash', item)"
                >
                  <History v-if="trash" :size="16" /><Trash2
                    v-else
                    :size="16"
                  />
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-if="files.data.value?.has_more || cursor" class="pagination">
      <button
        class="button secondary small"
        :disabled="!cursor"
        @click="cursor = null"
      >
        Về đầu</button
      ><button
        class="button secondary small"
        :disabled="!files.data.value?.has_more"
        @click="cursor = files.data.value?.next_cursor ?? null"
      >
        Trang tiếp <ChevronRight :size="15" />
      </button>
    </div>
  </section>
  <div class="intro-strip">
    <History :size="23" />
    <p>
      <strong>Không ghi đè lịch sử.</strong> Mỗi lần lưu tạo một phiên bản. Khôi
      phục bản cũ sẽ tạo phiên bản mới; tài liệu đã ghim trong hồ sơ không bị
      thay đổi.
    </p>
  </div>
  <ModalDialog
    v-if="modal"
    :title="
      modal === 'upload'
        ? 'Tải tài liệu lên'
        : modal === 'folder'
          ? 'Tạo thư mục'
          : modal === 'document'
            ? 'Tạo tài liệu mới'
            : modal === 'rename'
              ? 'Tên và vị trí tài liệu'
              : modal === 'labels'
                ? 'Nhãn tài liệu'
                : modal === 'copy'
                  ? 'Tạo bản sao'
                  : modal === 'share'
                    ? 'Chia sẻ tài liệu'
                    : modal === 'trash'
                      ? trash
                        ? 'Khôi phục tài liệu'
                        : 'Đưa vào thùng rác'
                      : modal === 'folder-rename'
                        ? 'Tên và vị trí thư mục'
                        : modal === 'folder-share'
                          ? 'Chia sẻ quyền kế thừa'
                          : 'Lịch sử phiên bản'
    "
    @close="close"
  >
    <div v-if="error" class="notice error error-inline" role="alert">
      <div>
        {{ errorText(error)
        }}<code v-if="error instanceof ApiError && error.traceId">{{
          error.traceId
        }}</code
        ><button
          v-if="error instanceof ApiError && error.status === 409"
          class="button secondary small"
          style="margin-top: 10px"
          @click="
            () => {
              refresh()
              close()
            }
          "
        >
          Tải lại danh sách
        </button>
      </div>
    </div>
    <form v-if="modal !== 'versions'" @submit.prevent="save">
      <div class="stack">
        <template
          v-if="
            modal === 'folder' ||
            modal === 'document' ||
            modal === 'rename' ||
            modal === 'folder-rename' ||
            modal === 'labels' ||
            modal === 'copy'
          "
          ><div v-if="modal === 'labels' || modal === 'copy'" class="field">
            <label for="labels">Nhãn</label
            ><input
              id="labels"
              v-model="labelText"
              maxlength="500"
              placeholder="Ví dụ: Hợp đồng, Khẩn, Mẫu"
            />
            <small
              >Ngăn cách bằng dấu phẩy. Tên trùng chỉ khác chữ hoa được tính là một
              nhãn.</small
            >
            <ul v-if="parseLabels(labelText).length" class="label-chips">
              <li v-for="label in parseLabels(labelText)" :key="label">
                {{ label }}
              </li>
            </ul>
          </div>
          <div v-if="modal === 'copy'" class="field">
            <label for="copy-name">Tên bản sao</label
            ><input
              id="copy-name"
              v-model="name"
              maxlength="255"
              placeholder="Để trống thì giữ nguyên tên gốc"
            />
            <small>Giữ nguyên phần mở rộng của bản gốc.</small>
          </div>
          <div v-if="modal === 'copy'" class="field">
            <label for="copy-folder">Thư mục đích</label
            ><select id="copy-folder" v-model="targetFolder">
              <option value="">Tài liệu / thư mục gốc</option>
              <option
                v-for="item in folders.data.value?.items"
                :key="item.id"
                :value="item.id"
              >
                {{ item.name }}
              </option></select
            ><small>Chỉ các thư mục bạn được phép ghi.</small>
          </div>
          <p v-if="modal === 'copy' && copyPreview" class="muted">
            {{ copySummary(copyPreview) }}
          </p>
          <div v-if="modal === 'folder' || modal === 'document' || modal === 'rename' || modal === 'folder-rename'" class="field">
            <label for="file-name">{{
              modal === 'folder' || modal === 'folder-rename'
                ? 'Tên thư mục'
                : 'Tên tài liệu'
            }}</label
            ><input
              id="file-name"
              v-model="name"
              required
              maxlength="255"
              autofocus
              placeholder="Ví dụ: Báo cáo công tác tháng 10"
            />
          </div>
          <div v-if="modal === 'document'" class="field">
            <label for="document-kind">Loại tài liệu</label
            ><select id="document-kind" v-model="kind">
              <option value="docx">Văn bản · DOCX</option>
              <option value="xlsx">Bảng tính · XLSX</option>
              <option value="pptx">Trình chiếu · PPTX</option>
            </select>
          </div>
          <div v-if="modal === 'rename' || modal === 'folder-rename'" class="field">
            <label for="target-folder">Thư mục đích</label
            ><select id="target-folder" v-model="targetFolder">
              <option value="">Tài liệu / thư mục gốc</option>
              <option
                v-for="item in folders.data.value?.items"
                :key="item.id"
                :value="item.id"
              >
                {{ item.name }}
              </option></select
            ><small>Quyền kế thừa được tính lại khi di chuyển.</small>
          </div></template
        ><template v-if="modal === 'upload'"
          ><label for="upload-file" class="notice"
            ><Upload :size="22" /><span
              >Chọn tệp từ máy tính. Hệ thống chỉ báo hoàn tất sau khi đã lưu
              phiên bản bền vững.</span
            ></label
          ><input
            id="upload-file"
            type="file"
            required
            :disabled="busy"
            @change="pickFile"
          />
          <div v-if="uploadFile" class="primary-cell">
            <File :size="22" />
            <div>
              <strong>{{ uploadFile.name }}</strong
              ><small>{{ formatSize(uploadFile.size) }}</small>
            </div>
            <button
              v-if="!busy"
              type="button"
              class="icon-button"
              aria-label="Bỏ tệp đã chọn"
              @click="uploadFile = null"
            >
              <X :size="16" />
            </button>
          </div>
          <div v-if="busy" class="upload-progress" role="status">
            <progress :value="progress ?? undefined" :max="100" />
            <p class="muted">Đang tải và hoàn tất tiếp nhận…</p>
          </div></template
        ><template v-if="modal === 'share' || modal === 'folder-share'"
          ><p class="muted">
            {{
              modal === 'folder-share'
                ? 'Người nhận thừa hưởng quyền này với mọi tài liệu bên trong'
                : 'Chỉ chia sẻ quyền mà bạn đang có trên'
            }}
            <strong>{{
              modal === 'folder-share'
                ? selectedFolder?.name
                : selected?.name
            }}</strong
            >{{ modal === 'folder-share' ? ', kể cả thư mục con sau này.' : '.' }}
          </p>
          <div v-if="modal === 'folder-share'" class="field">
            <label>Đang chia sẻ</label>
            <StatePanel
              :loading="folderShares.isPending.value"
              :error="folderShares.error.value"
              :empty="folderShares.data.value?.items.length === 0"
              title="Chưa chia sẻ thư mục này"
              description="Mọi người dùng khác không truy cập được nội dung bên trong."
            />
            <ul class="share-list">
              <li
                v-for="share in folderShares.data.value?.items"
                :key="share.id"
              >
                <span>{{ shareLabel(share) }}</span>
                <button
                  class="button secondary small"
                  type="button"
                  :disabled="busy"
                  @click="
                    () => {
                      userId = share.user_id
                      access = 'none'
                    }
                  "
                >
                  Thu hồi
                </button>
              </li>
            </ul>
          </div>
          <div class="field">
            <label for="share-user">Người nhận</label
            ><select id="share-user" v-model="userId" required>
              <option value="">Chọn thành viên</option>
              <option
                v-for="user in users.data.value?.items"
                :key="user.id"
                :value="user.id"
              >
                {{ user.display_name }}
              </option>
            </select>
          </div>
          <div class="field">
            <label for="share-access">Quyền truy cập</label
            ><select id="share-access" v-model="access">
              <option value="read">Được xem và tải</option>
              <option value="write">Được chỉnh sửa</option>
              <option value="none">Thu hồi quyền chia sẻ</option>
            </select>
          </div>
          <div class="notice warning">
            <span v-if="modal === 'folder-share'"
              >Quyền trên thư mục có kế thừa và chỉ chủ sở hữu thư mục được thay
              đổi. Sau khi lưu, quyền được cấp lại trên từng tài liệu bên
              trong.</span
            ><span v-else
              >Thu hồi quyền sẽ chặn yêu cầu tải mới; đường dẫn đã cấp có thời hạn
              hiệu lực ngắn theo chính sách hệ thống.</span
            >
          </div>
          <div v-if="modal === 'folder-share'" class="notice">
            <span
              >Sau khi chia sẻ, tài liệu có thể tạm thời trả về
              <code>409</code> trong lúc hệ thống cấp lại quyền. Mở lại danh sách
              sau vài giây.</span
            >
          </div></template
        ><template v-if="modal === 'trash'"
          ><p>
            {{ trash ? 'Khôi phục' : 'Đưa' }}
            <strong>{{ selected?.name }}</strong>
            {{ trash ? 'về kho tài liệu?' : 'vào thùng rác?' }}
          </p>
          <p class="muted">
            Các phiên bản đã ghim vào hồ sơ vẫn được giữ lại.
          </p></template
        >
      </div>
      <div class="form-actions">
        <button
          class="button secondary"
          type="button"
          :disabled="busy"
          @click="close"
        >
          Hủy</button
        ><button class="button" :disabled="busy">
          {{
            busy
              ? 'Đang xử lý…'
              : modal === 'upload'
                ? 'Tải lên'
                : modal === 'share' || modal === 'folder-share'
                  ? 'Lưu quyền chia sẻ'
                  : modal === 'copy'
                    ? 'Tạo bản sao'
                    : modal === 'labels'
                      ? 'Lưu nhãn'
                      : modal === 'trash'
                        ? trash
                          ? 'Khôi phục'
                          : 'Đưa vào thùng rác'
                        : 'Lưu'
          }}
        </button>
      </div>
    </form>
    <template v-else
      ><p class="muted" style="margin-bottom: 15px">{{ selected?.name }}</p>
      <StatePanel
        :loading="versionQuery.isPending.value"
        :error="versionQuery.error.value"
        :empty="versionQuery.data.value?.items.length === 0"
        @retry="versionQuery.refetch()"
      />
      <div
        v-for="version in versionQuery.data.value?.items"
        :key="version.id"
        class="list-row"
        style="padding: 15px 0"
      >
        <span class="file-icon"><History :size="17" /></span>
        <div class="grow">
          <p>Phiên bản {{ version.version_no }}</p>
          <small
            >{{ formatDate(version.created_at, true) }} ·
            {{ formatSize(version.size ?? 0) }}</small
          ><small class="mono">{{ version.checksum?.slice(0, 20) }}</small>
        </div>
        <button
          class="button secondary small"
          :disabled="busy"
          @click="restore(version)"
        >
          Khôi phục bản này
        </button>
      </div></template
    >
  </ModalDialog>
</template>
