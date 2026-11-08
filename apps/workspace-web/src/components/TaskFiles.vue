<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { ref } from 'vue'
import { Download, Eye, FileText, FolderOpen, Paperclip, Trash2, Upload } from 'lucide-vue-next'
import { formatSize } from '@dx/web-shared/api.ts'
import type { DriveFile } from '@dx/web-shared/types.ts'
import { api } from '../api'
import { useSession } from '../stores/session'
import { toast } from '../ui/toast'
import { previewKind } from '../ui/preview'
import FilePreview from './FilePreview.vue'
import DrivePicker from './DrivePicker.vue'
import { mergeIds, uploadToDrive, type AttachedFile } from './attachments'

/**
 * Files on a task: the brief from whoever gave it and the results handed in. Everyone on the
 * task opens them through the task; the person doing it may add files and remove their own.
 */
const props = defineProps<{
  taskId: string
  files: AttachedFile[]
  revision: number
  closed: boolean
  canManage: boolean
  isAssignee: boolean
}>()
const emit = defineEmits<{ changed: [] }>()
const session = useSession()
const canAttach = () => !props.closed && (props.canManage || props.isAssignee)
const canRemove = (file: AttachedFile) =>
  !props.closed && (props.canManage || (props.isAssignee && file.owner_id === session.user?.id))
const busy = ref(false)
const picking = ref(false)
const picker = ref<HTMLInputElement>()
const preview = ref<AttachedFile | null>(null)

async function save(ids: string[], message: string) {
  await api.request(`/tasks/${props.taskId}`, {
    method: 'PATCH',
    body: JSON.stringify({ expected_revision: props.revision, file_ids: ids }),
  })
  toast.success(message)
  emit('changed')
}
async function uploadPicked(event: Event) {
  const input = event.target as HTMLInputElement
  const chosen = [...(input.files ?? [])]
  input.value = ''
  if (!chosen.length) return
  busy.value = true
  try {
    const uploaded = []
    for (const file of chosen) uploaded.push(await uploadToDrive(file))
    await save(
      mergeIds(props.files.map((f) => f.id), uploaded.map((f) => f.id)),
      `Đã đính kèm ${uploaded.length} tệp (lưu trong Tài liệu của tôi)`,
    )
  } catch (error) {
    toast.error(error)
  } finally {
    busy.value = false
  }
}
async function attachFromDrive(files: DriveFile[]) {
  picking.value = false
  busy.value = true
  try {
    await save(mergeIds(props.files.map((f) => f.id), files.map((f) => f.id)), `Đã đính kèm ${files.length} tệp`)
  } catch (error) {
    toast.error(error)
  } finally {
    busy.value = false
  }
}
async function remove(file: AttachedFile) {
  if (!window.confirm(`Gỡ “${file.name ?? 'tệp'}” khỏi công việc? Tệp vẫn còn trong kho tài liệu.`)) return
  busy.value = true
  try {
    await save(props.files.filter((f) => f.id !== file.id).map((f) => f.id), 'Đã gỡ tệp khỏi công việc')
  } catch (error) {
    toast.error(error)
  } finally {
    busy.value = false
  }
}
async function link(file: AttachedFile) {
  const ticket = await api.request<{ url: string }>(`/tasks/${props.taskId}/files/${file.id}/download`, {
    method: 'POST',
  })
  return ticket.url
}
async function download(file: AttachedFile) {
  try {
    window.location.assign(await link(file))
  } catch (error) {
    toast.error(error)
  }
}
</script>
<template>
  <section class="card">
    <header class="card-header">
      <h2><Paperclip :size="18" /> Tài liệu</h2>
      <div v-if="canAttach()" class="inline-actions">
        <button class="button secondary small" :disabled="busy" @click="picker?.click()">
          <Upload :size="14" />{{ busy ? 'Đang tải lên…' : 'Tải tệp lên' }}
        </button>
        <button class="button secondary small" :disabled="busy" @click="picking = true">
          <FolderOpen :size="14" />Chọn từ kho
        </button>
        <input ref="picker" type="file" multiple hidden @change="uploadPicked" />
      </div>
    </header>
    <p v-if="!files.length" class="step-empty" style="padding: 18px 23px">
      Chưa có tài liệu.<template v-if="canAttach()">
        {{ ' ' }}{{ canManage ? 'Đính kèm yêu cầu, mẫu biểu cho người làm.' : 'Đính kèm kết quả trước khi nộp.' }}</template
      >
    </p>
    <div v-for="file in files" :key="file.id" class="list-row">
      <FileText :size="18" />
      <div class="grow">
        <template v-if="file.restricted"><p class="muted">Tệp đã bị xóa khỏi kho tài liệu</p></template>
        <template v-else>
          <p>{{ file.name }}</p>
          <small class="muted">{{ formatSize(file.size ?? 0) }}<template v-if="file.owner_name"> · {{ file.owner_name }}</template></small>
        </template>
      </div>
      <template v-if="!file.restricted">
        <button
          v-if="previewKind(file.name ?? '', file.mime)"
          class="icon-button"
          :aria-label="`Xem ${file.name}`"
          title="Xem"
          @click="preview = file"
        >
          <Eye :size="16" />
        </button>
        <button class="icon-button" :aria-label="`Tải ${file.name}`" title="Tải về" @click="download(file)">
          <Download :size="16" />
        </button>
      </template>
      <button
        v-if="canRemove(file)"
        class="icon-button"
        :aria-label="`Gỡ ${file.name ?? 'tệp'}`"
        title="Gỡ khỏi công việc"
        :disabled="busy"
        @click="remove(file)"
      >
        <Trash2 :size="16" />
      </button>
    </div>
  </section>
  <DrivePicker v-if="picking" :exclude="files.map((f) => f.id)" @close="picking = false" @picked="attachFromDrive" />
  <FilePreview
    v-if="preview"
    :key="preview.id"
    :name="preview.name ?? ''"
    :mime="preview.mime"
    :source="() => link(preview!)"
    :download="() => download(preview!)"
    @close="preview = null"
  />
</template>
