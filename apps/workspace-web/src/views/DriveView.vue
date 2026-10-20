<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import {
  ArrowDownUp,
  ChevronRight,
  Copy,
  Download,
  File,
  FilePlus2,
  FileSpreadsheet,
  FileText,
  FolderClosed,
  FolderPlus,
  Grid2X2,
  History,
  List,
  MoreVertical,
  PanelLeftClose,
  PanelLeftOpen,
  Pencil,
  Plus,
  Presentation,
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
const railCollapsed = ref(window.localStorage.getItem('dx-drive-rail-collapsed') === '1')
function toggleRailCollapsed() {
  railCollapsed.value = !railCollapsed.value
  window.localStorage.setItem('dx-drive-rail-collapsed', railCollapsed.value ? '1' : '0')
}
const newMenuOpen = ref(false)
const fileMenuId = ref<string | null>(null)
const viewMode = ref<'list' | 'grid'>('list')
const sortBy = ref<'name' | 'created' | 'size'>('created')
const sortDescending = ref(true)
const dragging = ref(false)
const cursor = ref<string | null>(null)
const files = useQuery({
  queryKey: computed(() => [
    'drive',
    folder.value,
    searchQuery.value,
    trash.value,
    cursor.value,
    sortBy.value,
    sortDescending.value,
  ]),
  queryFn: () =>
    api.request<Page<DriveFile>>(
      `/drive/files${queryString({ folder_id: folder.value, q: searchQuery.value, trash: trash.value, cursor: cursor.value, sort_by: sortBy.value, descending: sortDescending.value })}`,
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
const visibleFiles = computed(() => files.data.value?.items ?? [])
const activeFile = computed(() => visibleFiles.value.find(item => item.id === fileMenuId.value) ?? null)
const sortedFolders = computed(() => [...(folders.data.value?.items ?? [])].sort((a, b) => a.name.localeCompare(b.name, 'vi')))
const currentLocation = computed(() => trash.value ? 'Thùng rác' : searchQuery.value ? 'Kết quả tìm kiếm' : crumbs.value.at(-1)?.name ?? 'Tài liệu của tôi')
watch(sortBy, value => { sortDescending.value = value !== 'name'; cursor.value = null })
watch(sortDescending, () => { cursor.value = null })
function fileKind(item: DriveFile) {
  const extension = item.name.split('.').at(-1)?.toLowerCase()
  if (['doc', 'docx', 'odt'].includes(extension ?? '')) return 'Văn bản'
  if (['xls', 'xlsx', 'ods', 'csv'].includes(extension ?? '')) return 'Bảng tính'
  if (['ppt', 'pptx', 'odp'].includes(extension ?? '')) return 'Trình chiếu'
  if (extension === 'pdf') return 'PDF'
  if (item.mime?.startsWith('image/')) return 'Hình ảnh'
  return 'Tệp'
}
function fileIcon(item: DriveFile) {
  const kind = fileKind(item)
  return kind === 'Bảng tính' ? FileSpreadsheet : kind === 'Trình chiếu' ? Presentation : kind === 'Tệp' ? File : FileText
}
function fileTone(item: DriveFile) {
  const kind = fileKind(item)
  return kind === 'Bảng tính' ? 'sheet' : kind === 'Trình chiếu' ? 'slide' : kind === 'PDF' ? 'pdf' : kind === 'Hình ảnh' ? 'image' : 'document'
}
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
  newMenuOpen.value = false
  fileMenuId.value = null
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
  fileMenuId.value = null
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
  trash.value = false
  search.value = ''
  searchQuery.value = ''
  folder.value = item.id
  crumbs.value.push(item)
  cursor.value = null
}
function go(index: number) {
  trash.value = false
  search.value = ''
  searchQuery.value = ''
  crumbs.value = crumbs.value.slice(0, index + 1)
  folder.value = index < 0 ? null : crumbs.value[index]!.id
  cursor.value = null
}
function showTrash(value: boolean) {
  trash.value = value
  cursor.value = null
  fileMenuId.value = null
}
function openNew(type: 'folder' | 'document' | 'upload') {
  open(type)
}
function toggleFileMenu(item: DriveFile) {
  fileMenuId.value = fileMenuId.value === item.id ? null : item.id
}
function onDrop(event: DragEvent) {
  dragging.value = false
  const dropped = event.dataTransfer?.files?.[0]
  if (!dropped || trash.value) return
  open('upload')
  uploadFile.value = dropped
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
  <header class="drive-hero">
    <div>
      <span class="eyebrow">KHÔNG GIAN TÀI LIỆU</span>
      <h1>Tài liệu</h1>
      <p>Tìm, sắp xếp và cộng tác trên tài liệu của bạn.</p>
    </div>
    <label class="drive-search"><Search :size="20" /><span class="sr-only">Tìm tài liệu trong toàn kho</span>
      <input v-model="search" type="search" placeholder="Tìm trong toàn bộ tài liệu" />
      <button v-if="search" type="button" aria-label="Xóa từ khóa" @click="search = ''"><X :size="17" /></button>
    </label>
  </header>
  <div v-if="error && !modal" class="notice error error-inline" role="alert">
    {{ errorText(error) }}
  </div>
  <div class="drive-workspace" :class="{ 'rail-collapsed': railCollapsed }">
    <aside class="drive-rail" aria-label="Điều hướng tài liệu">
      <div class="drive-new-wrap">
        <button class="drive-new" :aria-expanded="newMenuOpen" aria-label="Mới" title="Mới" @click="newMenuOpen = !newMenuOpen"><Plus :size="22" /><span>Mới</span></button>
        <div v-if="newMenuOpen" class="drive-new-menu">
          <button @click="openNew('folder')"><FolderPlus :size="18" /> Thư mục mới</button>
          <button @click="openNew('upload')"><Upload :size="18" /> Tải tệp lên</button>
          <button @click="openNew('document')"><FilePlus2 :size="18" /> Tài liệu mới</button>
        </div>
      </div>
      <nav class="drive-nav" aria-label="Vị trí tài liệu">
        <button :class="{ active: !trash && !folder && !searchQuery }" aria-label="Tài liệu của tôi" title="Tài liệu của tôi" @click="go(-1)"><FolderClosed :size="19" /><span>Tài liệu của tôi</span></button>
        <button :class="{ active: trash }" aria-label="Thùng rác" title="Thùng rác" @click="showTrash(true)"><Trash2 :size="19" /><span>Thùng rác</span></button>
      </nav>
      <div v-if="!trash && !searchQuery && sortedFolders.length" class="drive-rail-folders">
        <span>THƯ MỤC Ở ĐÂY</span>
        <button v-for="item in sortedFolders" :key="item.id" @click="enter(item)"><FolderClosed :size="17" />{{ item.name }}</button>
      </div>
      <p class="drive-rail-note">Kéo tệp vào vùng danh sách để tải lên thư mục đang mở.</p>
    </aside>
    <section class="drive-panel" aria-label="Nội dung tài liệu" :class="{ 'drag-over': dragging }" @dragenter.prevent="dragging = true" @dragover.prevent @dragleave.prevent="dragging = false" @drop.prevent="onDrop">
      <div class="drive-panel-head">
        <div><span class="eyebrow">{{ trash ? 'ĐÃ XÓA' : searchQuery ? 'TÌM KIẾM' : 'KHÔNG GIAN CỦA BẠN' }}</span><h2>{{ currentLocation }}</h2></div>
        <div class="drive-panel-controls">
          <button class="drive-control drive-rail-toggle" :aria-label="railCollapsed ? 'Mở rộng cột tài liệu' : 'Thu gọn cột tài liệu'" :title="railCollapsed ? 'Mở rộng cột tài liệu' : 'Thu gọn cột tài liệu'" :aria-expanded="!railCollapsed" @click="toggleRailCollapsed"><PanelLeftOpen v-if="railCollapsed" :size="18" /><PanelLeftClose v-else :size="18" /></button>
          <label class="drive-sort"><span class="sr-only">Sắp xếp</span><select v-model="sortBy"><option value="created">Được thêm gần đây</option><option value="name">Tên</option><option value="size">Dung lượng</option></select></label>
          <button class="drive-control" :aria-label="sortDescending ? 'Sắp xếp tăng dần' : 'Sắp xếp giảm dần'" @click="sortDescending = !sortDescending"><ArrowDownUp :size="17" /></button>
          <span class="drive-control-divider" />
          <button class="drive-control" :class="{ active: viewMode === 'list' }" aria-label="Xem danh sách" :aria-pressed="viewMode === 'list'" @click="viewMode = 'list'"><List :size="18" /></button>
          <button class="drive-control" :class="{ active: viewMode === 'grid' }" aria-label="Xem dạng lưới" :aria-pressed="viewMode === 'grid'" @click="viewMode = 'grid'"><Grid2X2 :size="18" /></button>
        </div>
      </div>
      <p v-if="anyFolderSyncing" class="notice drive-sync" role="status">Đang cấp lại quyền sau thay đổi chia sẻ hoặc di chuyển thư mục. Tài liệu có thể tạm thời chưa mở được.</p>
    <div v-if="!trash && !searchQuery" class="drive-location">
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
      v-if="!trash && !searchQuery && sortedFolders.length"
      class="folder-grid"
    >
      <div
        v-for="item in sortedFolders"
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
      :empty="visibleFiles.length === 0 && (trash || !!searchQuery || !sortedFolders.length)"
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
    <div v-if="visibleFiles.length && viewMode === 'list'" class="table-wrap drive-table-wrap">
      <table class="drive-table">
        <thead>
          <tr>
            <th>Tên tài liệu</th>
            <th>Ngày thêm</th>
            <th>Dung lượng</th>
            <th><span class="sr-only">Thao tác</span></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in visibleFiles" :key="item.id">
            <td>
              <div class="primary-cell">
                <span class="file-icon drive-file-icon" :class="fileTone(item)"><component :is="fileIcon(item)" :size="19" /></span>
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
                  ><button v-else-if="!trash" class="drive-file-name" @click="download(item)">{{ item.name }}</button
                  ><strong v-else>{{ item.name }}</strong
                  ><small>{{ fileKind(item) }} · bản sửa {{ item.revision }}</small>
                  <ul v-if="item.labels?.length" class="label-chips">
                    <li v-for="label in item.labels" :key="label">
                      {{ label }}
                    </li>
                  </ul>
                </div>
              </div>
            </td>
            <td class="muted">
              {{ formatDate(item.created_at, true) }}
            </td>
            <td class="muted">{{ formatSize(item.size ?? 0) }}</td>
            <td>
              <div class="drive-row-actions">
                <button v-if="!trash" class="drive-control" :aria-label="`Tải ${item.name}`" @click="download(item)"><Download :size="17" /></button>
                <button v-if="!trash" class="drive-control" :aria-label="`Chia sẻ ${item.name}`" @click="open('share', item)"><Share2 :size="17" /></button>
                <button class="drive-control" :aria-label="`Thêm thao tác cho ${item.name}`" :aria-expanded="fileMenuId === item.id" @click="toggleFileMenu(item)"><MoreVertical :size="18" /></button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-if="visibleFiles.length && viewMode === 'grid'" class="drive-file-grid">
      <article v-for="item in visibleFiles" :key="item.id" class="drive-file-card">
        <div class="drive-file-card-top"><span class="drive-file-icon" :class="fileTone(item)"><component :is="fileIcon(item)" :size="20" /></span>
          <button class="drive-control" :aria-label="`Thêm thao tác cho ${item.name}`" :aria-expanded="fileMenuId === item.id" @click="toggleFileMenu(item)"><MoreVertical :size="18" /></button></div>
        <div class="drive-file-preview" :class="fileTone(item)"><component :is="fileIcon(item)" :size="45" :stroke-width="1.3" /></div>
        <div class="drive-file-card-bottom"><div class="grow"><RouterLink v-if="!trash && /\.(docx|xlsx|pptx|doc|xls|ppt|odt|ods|odp)$/i.test(item.name)" :to="`/drive/${item.id}/edit`" class="row-link">{{ item.name }}</RouterLink><button v-else-if="!trash" class="drive-file-name" @click="download(item)">{{ item.name }}</button><strong v-else>{{ item.name }}</strong><small>{{ formatDate(item.created_at) }} · {{ formatSize(item.size ?? 0) }}</small></div></div>
      </article>
    </div>
    <div v-if="activeFile" class="drive-action-bar">
      <span class="grow">{{ activeFile.name }}</span>
      <button v-if="!trash" @click="download(activeFile)"><Download :size="16" /> Tải xuống</button>
      <button v-if="!trash" @click="open('labels', activeFile)"><Tags :size="16" /> Nhãn</button>
      <button v-if="!trash" @click="open('copy', activeFile)"><Copy :size="16" /> Sao chép</button>
      <button v-if="!trash" @click="open('versions', activeFile)"><History :size="16" /> Phiên bản</button>
      <button v-if="!trash" @click="open('rename', activeFile)"><Pencil :size="16" /> Đổi tên / di chuyển</button>
      <button v-if="!trash" @click="open('share', activeFile)"><Share2 :size="16" /> Chia sẻ</button>
      <button @click="open('trash', activeFile)"><Trash2 :size="16" /> {{ trash ? 'Khôi phục' : 'Xóa' }}</button>
      <button aria-label="Đóng thao tác" @click="fileMenuId = null"><X :size="16" /></button>
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
<style scoped>
.drive-hero { display: flex; align-items: end; justify-content: space-between; gap: 24px; margin-bottom: 25px; }
.drive-hero h1 { margin: 4px 0 0; }
.drive-hero p { margin-top: 5px; color: var(--muted); }
.drive-search { display: flex; align-items: center; gap: 12px; width: min(440px, 48%); min-height: 48px; padding: 0 15px; background: #edf3f7; border: 1px solid transparent; border-radius: 25px; color: #688198; }
.drive-search:focus-within { background: #fff; border-color: #8bc4d0; box-shadow: 0 0 0 3px #dff2f5; }
.drive-search input { flex: 1; min-width: 0; background: transparent; border: 0; outline: 0; box-shadow: none; padding: 8px 0; color: var(--navy); }
.drive-search button { display: grid; place-items: center; border: 0; background: transparent; color: inherit; cursor: pointer; }
.drive-workspace { display: grid; grid-template-columns: 185px minmax(0, 1fr); gap: 18px; align-items: start; min-height: 580px; }
.drive-rail { position: sticky; top: 18px; padding: 5px 0; min-width: 0; }
.drive-new-wrap { position: relative; margin: 0 8px 24px; }
.drive-new { display: flex; align-items: center; gap: 12px; min-height: 52px; padding: 0 22px; border: 1px solid #d8e4ea; border-radius: 17px; background: #fff; color: var(--navy); box-shadow: 0 3px 10px #102d4620; font-weight: 700; cursor: pointer; }
.drive-new:hover { background: #f4fafb; border-color: #b9d9df; }
.drive-new-menu { position: absolute; top: 60px; left: 0; z-index: 15; min-width: 210px; padding: 7px; border: 1px solid var(--border); border-radius: 12px; background: #fff; box-shadow: 0 16px 38px #0d2e4530; }
.drive-new-menu button, .drive-nav button, .drive-rail-folders button { display: flex; align-items: center; gap: 13px; width: 100%; border: 0; background: none; color: var(--navy); cursor: pointer; text-align: left; }
.drive-new-menu button { padding: 11px 12px; border-radius: 8px; font-size: 13px; }
.drive-new-menu button:hover, .drive-rail-folders button:hover { background: #eef5f8; }
.drive-nav { display: grid; gap: 3px; }
.drive-nav button { min-height: 42px; padding: 0 14px; border-radius: 0 20px 20px 0; font-size: 13px; font-weight: 600; }
.drive-nav button:hover { background: #eaf1f5; }
.drive-nav button.active { background: #dcebf0; color: #145a69; }
.drive-rail-folders { margin-top: 26px; border-top: 1px solid var(--border); padding-top: 17px; }
.drive-rail-folders > span { display: block; padding: 0 13px 9px; font-size: 10px; font-weight: 700; letter-spacing: .1em; color: var(--muted); }
.drive-rail-folders button { padding: 9px 13px; border-radius: 8px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 12px; }
.drive-rail-folders svg { flex: none; color: #b5944b; }
.drive-rail-note { margin: 24px 13px; font-size: 12px; line-height: 1.55; color: var(--muted); }
@media (min-width: 701px) {
  .drive-workspace { transition: grid-template-columns 0.2s ease; }
  .drive-workspace.rail-collapsed { grid-template-columns: 64px minmax(0, 1fr); }
  .rail-collapsed .drive-new-wrap { margin: 0 4px 24px; }
  .rail-collapsed .drive-new { justify-content: center; width: 52px; padding: 0; }
  .rail-collapsed .drive-new > span,
  .rail-collapsed .drive-nav button > span,
  .rail-collapsed .drive-rail-folders,
  .rail-collapsed .drive-rail-note { display: none; }
  .rail-collapsed .drive-nav button { justify-content: center; padding: 0; border-radius: 12px; }
}
.drive-panel { min-width: 0; min-height: 570px; position: relative; border: 1px solid var(--border); border-radius: 14px; background: #fff; overflow: hidden; box-shadow: 0 5px 22px #152f4209; }
.drive-panel.drag-over { outline: 3px dashed #4098a6; outline-offset: -9px; background: #f5fbfc; }
.drive-panel-head { display: flex; align-items: center; justify-content: space-between; gap: 16px; min-height: 84px; padding: 18px 23px; }
.drive-panel-head h2 { margin: 3px 0 0; font-size: 20px; }
.drive-panel-controls { display: flex; align-items: center; gap: 5px; }
.drive-sort select { min-height: 35px; max-width: 125px; border: 0; background: transparent; color: var(--navy); font-size: 12px; cursor: pointer; }
.drive-control { width: 34px; height: 34px; display: grid; place-items: center; border: 0; border-radius: 7px; background: transparent; color: #60788b; cursor: pointer; }
.drive-control:hover, .drive-control.active { background: #e8f1f5; color: #135969; }
.drive-control-divider { height: 21px; width: 1px; background: var(--border); margin: 0 5px; }
.drive-sync { margin: 0 20px 12px; }
.drive-panel :deep(.drive-location) { padding: 10px 23px 16px; border-bottom: 0; }
.drive-panel :deep(.folder-grid) { padding: 12px 23px 24px; gap: 12px; }
.drive-panel :deep(.folder-card) { border-radius: 10px; background: #f9fbfc; }
.drive-panel :deep(.folder-card:hover) { background: #edf7f9; }
.drive-table th { background: #fff; text-transform: none; }
.drive-table td, .drive-table th { padding-left: 23px; padding-right: 16px; }
.drive-table tbody tr:hover { background: #f4f8fa; }
.drive-table .primary-cell { min-width: 230px; }
.drive-file-name { display: block; max-width: 100%; padding: 0; border: 0; background: transparent; color: var(--navy); font: inherit; font-weight: 700; text-align: left; cursor: pointer; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.drive-file-name:hover { color: #157482; text-decoration: underline; }
.drive-file-icon { border-radius: 8px; background: #e8f1f5; color: #36798a; }
.drive-file-icon.sheet { background: #e5f4eb; color: #288057; }
.drive-file-icon.slide { background: #fff0e4; color: #b97232; }
.drive-file-icon.pdf { background: #fae9e7; color: #ba5147; }
.drive-file-icon.image { background: #f0eafb; color: #7e5ab5; }
.drive-row-actions { display: flex; align-items: center; justify-content: flex-end; gap: 2px; }
.drive-file-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 16px; padding: 18px 23px 28px; border-top: 1px solid var(--border); }
.drive-file-card { border: 1px solid #dce5eb; border-radius: 12px; overflow: hidden; min-width: 0; background: #fff; }
.drive-file-card:hover { border-color: #a8cbd4; box-shadow: 0 6px 18px #102c4112; }
.drive-file-card-top { display: flex; justify-content: space-between; align-items: center; padding: 8px 10px 7px 15px; }
.drive-file-card-top .drive-file-icon { width: 29px; height: 29px; display: grid; place-items: center; }
.drive-file-preview { height: 118px; display: grid; place-items: center; color: #7aa7b3; background: linear-gradient(140deg, #f1f6f8, #eaf1f5); }
.drive-file-preview.sheet { color: #57a077; background: linear-gradient(140deg, #f0f8f3, #e4f1e9); }
.drive-file-preview.slide { color: #ca8f55; background: linear-gradient(140deg, #fff8ee, #f9ebdf); }
.drive-file-preview.pdf { color: #c8756f; background: linear-gradient(140deg, #fff7f5, #f8e8e5); }
.drive-file-preview.image { color: #987bc2; background: linear-gradient(140deg, #faf6ff, #ede6f8); }
.drive-file-card-bottom { display: flex; padding: 12px 15px 16px; min-width: 0; }
.drive-file-card-bottom .grow { min-width: 0; }
.drive-file-card-bottom strong, .drive-file-card-bottom .row-link, .drive-file-card-bottom .drive-file-name { display: block; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-size: 13px; }
.drive-file-card-bottom small { display: block; color: var(--muted); margin-top: 5px; font-size: 11px; }
.drive-action-bar { position: sticky; bottom: 12px; z-index: 8; display: flex; align-items: center; flex-wrap: wrap; gap: 4px; margin: 12px 18px; padding: 8px 10px 8px 17px; border: 1px solid #c9dfe6; border-radius: 12px; background: #e8f4f7; box-shadow: 0 7px 24px #183e5125; }
.drive-action-bar > span { min-width: 120px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; font-weight: 700; }
.drive-action-bar button { display: flex; align-items: center; gap: 5px; border: 0; border-radius: 7px; padding: 8px; color: #275363; background: transparent; cursor: pointer; font-size: 12px; }
.drive-action-bar button:hover { background: #d2e8ef; }
.drive-panel :deep(.pagination) { padding: 16px 23px; }
@media (max-width: 1100px) { .drive-workspace { grid-template-columns: 155px minmax(0, 1fr); gap: 10px; } .drive-panel-head { flex-wrap: wrap; } }
@media (max-width: 700px) { .drive-hero { flex-direction: column; align-items: stretch; } .drive-search { width: 100%; } .drive-workspace { display: block; } .drive-rail { position: static; display: flex; align-items: center; gap: 8px; margin-bottom: 12px; padding: 0; } .drive-new-wrap { margin: 0; } .drive-nav { display: flex; flex: 1; } .drive-nav button { min-height: 45px; padding: 0 10px; border-radius: 10px; justify-content: center; } .drive-rail-folders, .drive-rail-note, .drive-rail-toggle { display: none; } .drive-panel-head { padding: 16px; } .drive-panel :deep(.folder-grid) { padding: 10px 16px 17px; } .drive-file-grid { padding: 15px; } .drive-sort select { max-width: 105px; } }
</style>
