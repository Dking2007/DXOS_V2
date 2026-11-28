<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { computed, ref } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { FileText, Search } from 'lucide-vue-next'
import type { Page } from '@dx/web-shared/api.ts'
import { formatDate, formatSize } from '@dx/web-shared/api.ts'
import type { DriveFile } from '@dx/web-shared/types.ts'
import ModalDialog from '@dx/web-shared/components/ModalDialog.vue'
import StatePanel from '@dx/web-shared/components/StatePanel.vue'
import { api } from '../api'

/** Choose files already in the drive: recent ones at the top level, or any folder by name. */
const props = defineProps<{ exclude?: string[] }>()
const emit = defineEmits<{ close: []; picked: [files: DriveFile[]] }>()
const search = ref('')
const query = ref('')
const files = useQuery({
  queryKey: computed(() => ['drive', 'picker', query.value]),
  queryFn: () =>
    api.request<Page<DriveFile>>(
      `/drive/files?limit=50${query.value ? `&q=${encodeURIComponent(query.value)}` : ''}`,
    ),
})
const chosen = ref<string[]>([])
const items = computed(() => (files.data.value?.items ?? []).filter((f) => !props.exclude?.includes(f.id)))
function toggle(id: string) {
  chosen.value = chosen.value.includes(id) ? chosen.value.filter((x) => x !== id) : [...chosen.value, id]
}
function pick() {
  const all = files.data.value?.items ?? []
  emit(
    'picked',
    chosen.value.map((id) => all.find((f) => f.id === id)!).filter(Boolean),
  )
}
</script>
<template>
  <ModalDialog title="Chọn từ kho tài liệu" @close="emit('close')">
    <form class="search-box picker-search" role="search" @submit.prevent="query = search.trim()">
      <Search :size="16" /><input
        v-model="search"
        type="search"
        placeholder="Tìm theo tên tệp ở mọi thư mục…"
        aria-label="Tìm tệp"
      /><button class="button small">Tìm</button>
    </form>
    <StatePanel
      :loading="files.isPending.value"
      :error="files.error.value"
      :empty="!!files.data.value && !items.length"
      compact
      :title="query ? 'Không có tệp nào khớp' : 'Chưa có tệp ở thư mục gốc'"
      :description="query ? '' : 'Gõ tên để tìm trong mọi thư mục bạn được xem.'"
      @retry="files.refetch()"
    />
    <div v-if="items.length" class="picker-list">
      <label v-for="file in items" :key="file.id" class="list-row picker-row">
        <input type="checkbox" :checked="chosen.includes(file.id)" @change="toggle(file.id)" />
        <FileText :size="16" aria-hidden="true" class="picker-icon" />
        <span class="grow"
          ><span class="picker-name" :title="file.name">{{ file.name }}</span
          ><small class="muted">{{ formatSize(file.size ?? 0) }} · {{ formatDate(file.created_at) }}</small></span
        >
      </label>
    </div>
    <div class="form-actions">
      <button type="button" class="button secondary" @click="emit('close')">Hủy</button>
      <button
        type="button"
        class="button"
        :disabled="!chosen.length"
        :title="chosen.length ? '' : 'Chọn ít nhất một tệp.'"
        @click="pick"
      >
        {{ chosen.length ? `Đính kèm ${chosen.length} tệp` : 'Đính kèm tệp' }}
      </button>
    </div>
  </ModalDialog>
</template>
<style scoped>
.picker-search {
  margin-bottom: 12px;
}
.picker-list {
  max-height: min(50dvh, 420px);
  overflow-y: auto;
  border: 1px solid var(--border);
  border-radius: var(--radius);
}
.picker-row {
  cursor: pointer;
  padding: 12px 16px;
  gap: 12px;
}
.picker-icon {
  flex-shrink: 0;
  color: var(--muted);
}
.picker-name {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 600;
}
</style>
