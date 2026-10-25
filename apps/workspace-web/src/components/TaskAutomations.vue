<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { computed, ref } from 'vue'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { Workflow, Zap } from 'lucide-vue-next'
import { api } from '../api'
import { errorText } from '@dx/web-shared/api.ts'
const props = defineProps<{ taskId: string; closed: boolean }>()
interface Item {
  id: string
  name: string
  description: string
  trigger_label: string
  enabled: boolean
  attached: boolean
}
interface Listing {
  available: Item[]
  always: Item[]
  can_manage: boolean
}
const queryClient = useQueryClient()
const listing = useQuery({
  queryKey: computed(() => ['task-automations', props.taskId]),
  queryFn: () => api.request<Listing>(`/tasks/${props.taskId}/automations`),
})
const busy = ref<string | null>(null)
const error = ref<unknown>(null)
const editable = computed(() => !!listing.data.value?.can_manage && !props.closed)
async function toggle(item: Item) {
  busy.value = item.id
  error.value = null
  try {
    const result = await api.request<Listing>(`/tasks/${props.taskId}/automations/${item.id}`, {
      method: item.attached ? 'DELETE' : 'PUT',
    })
    queryClient.setQueryData(['task-automations', props.taskId], result)
    await queryClient.invalidateQueries({ queryKey: ['task', props.taskId] })
  } catch (cause) {
    error.value = cause
  } finally {
    busy.value = null
  }
}
</script>
<template>
  <section v-if="listing.data.value && (listing.data.value.available.length || listing.data.value.always.length)" class="card">
    <header class="card-header">
      <h3><Workflow :size="16" style="vertical-align: -3px" /> Luồng tự động</h3>
    </header>
    <div class="card-body task-flows">
      <p v-if="listing.data.value.available.length" class="muted task-flows-hint">
        {{
          editable
            ? 'Bật luồng muốn áp dụng cho công việc này. Luồng chạy tự động khi sự kiện xảy ra.'
            : 'Người giao, người phụ trách hoặc điều phối công việc mới gắn/gỡ được.'
        }}
      </p>
      <div v-for="item in listing.data.value.available" :key="item.id" class="task-flow">
        <div class="grow">
          <strong>{{ item.name }}</strong>
          <small
            >Chạy khi {{ item.trigger_label.toLowerCase() }}<template v-if="!item.enabled">
              · <span class="overdue-text">luồng đang tắt</span></template
            ></small
          >
          <small v-if="item.description" class="muted">{{ item.description }}</small>
        </div>
        <label class="switch" :title="item.attached ? 'Đang gắn' : 'Chưa gắn'"
          ><input
            type="checkbox"
            :checked="item.attached"
            :disabled="!editable || busy === item.id || (!item.enabled && !item.attached)"
            :aria-label="`${item.attached ? 'Gỡ' : 'Gắn'} luồng ${item.name}`"
            @change="toggle(item)" /><span
        /></label>
      </div>
      <div v-if="listing.data.value.always.length" class="task-flows-always">
        <span class="section-label"><Zap :size="12" /> Luôn áp dụng cho mọi công việc</span>
        <small v-for="item in listing.data.value.always" :key="item.id"
          >{{ item.name }} · khi {{ item.trigger_label.toLowerCase() }}</small
        >
      </div>
      <div v-if="error" class="notice error">{{ errorText(error) }}</div>
    </div>
  </section>
</template>
