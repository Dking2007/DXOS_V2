<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { ref } from 'vue'
import { Sparkles } from 'lucide-vue-next'
import { formatDate } from '@dx/web-shared/api.ts'
import { api } from '../api'
import { toast } from '../ui/toast'

/** AI proposes sub-tasks for a large task; the chosen ones are created as unassigned drafts. */
const props = defineProps<{ taskId: string; caseId?: string | null }>()
const emit = defineEmits<{ created: [] }>()
interface Item {
  title: string
  due_at: string | null
  note: string
  picked: boolean
}
const items = ref<Item[]>([])
const loading = ref(false)
const creating = ref(false)
async function suggest() {
  loading.value = true
  try {
    const result = await api.request<{ items: Omit<Item, 'picked'>[] }>(`/ai/tasks/${props.taskId}/breakdown`, { method: 'POST' })
    items.value = result.items.map((item) => ({ ...item, picked: true }))
    if (!items.value.length) toast.error('AI chưa đề xuất được việc con nào.')
  } catch (error) {
    toast.error(error)
  } finally {
    loading.value = false
  }
}
async function create() {
  creating.value = true
  const chosen = items.value.filter((item) => item.picked && item.title.trim())
  try {
    for (const item of chosen)
      await api.request('/tasks', {
        method: 'POST',
        body: JSON.stringify({
          title: item.title,
          description: item.note,
          due_at: item.due_at,
          parent_id: props.taskId,
          case_id: props.caseId ?? null,
        }),
      })
    toast.success(`Đã tạo ${chosen.length} việc con (chưa giao). Mở từng việc để giao người làm.`)
    items.value = []
    emit('created')
  } catch (error) {
    toast.error(error)
  } finally {
    creating.value = false
  }
}
</script>
<template>
  <div style="padding: 0 23px 16px">
    <button v-if="!items.length" class="button secondary small ai-action" :disabled="loading" @click="suggest">
      <Sparkles :size="14" />{{ loading ? 'AI đang chia việc…' : 'Gợi ý việc con bằng AI' }}
    </button>
    <div v-else class="ai-card">
      <header><span class="ai-title"><Sparkles :size="16" />Việc con AI đề xuất</span></header>
      <label v-for="(item, index) in items" :key="index" class="ai-issue" style="cursor: pointer">
        <input v-model="item.picked" type="checkbox" />
        <span class="grow"
          ><input v-model="item.title" maxlength="250" :aria-label="`Tên việc con ${index + 1}`" style="width: 100%" /><small
            class="muted"
            >{{ item.due_at ? `Hạn đề xuất ${formatDate(item.due_at, true)}` : 'Chưa có hạn' }}{{ item.note ? ` · ${item.note}` : '' }}</small
          ></span
        >
      </label>
      <div class="inline-actions" style="margin-top: 10px">
        <button class="button small" :disabled="creating || !items.some((i) => i.picked)" @click="create">
          {{ creating ? 'Đang tạo…' : `Tạo ${items.filter((i) => i.picked).length} việc con` }}
        </button>
        <button class="button ghost small" :disabled="creating" @click="items = []">Bỏ qua</button>
      </div>
    </div>
  </div>
</template>
