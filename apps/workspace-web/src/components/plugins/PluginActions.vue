<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<!-- Buttons a plugin adds to a dossier's or a task's actions ("Ký số", "Ghi giờ làm"). Each opens a
     dialog holding the plugin's frame, which ends it with "close" and may ask for a "refresh". -->
<script setup lang="ts">
import { computed, ref } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { Puzzle } from 'lucide-vue-next'
import ModalDialog from '@dx/web-shared/components/ModalDialog.vue'
import { api } from '../../api'
import PluginFrames from './PluginFrames.vue'
import type { PluginSlotItem } from './PluginFrames.vue'

const props = defineProps<{
  place: 'case.action' | 'task.action'
  context: { case_id?: string; task_id?: string }
}>()
const emit = defineEmits<{ done: [result: unknown] }>()
const slots = useQuery({
  queryKey: computed(() => ['plugin-slots', props.place]),
  queryFn: () => api.request<{ items: PluginSlotItem[] }>(`/plugin-slots?slot=${props.place}`).then((r) => r.items),
  staleTime: 60_000,
})
const open = ref<PluginSlotItem | null>(null)
function close(result: unknown) {
  open.value = null
  emit('done', result)
}
</script>
<template>
  <button
    v-for="item in slots.data.value ?? []"
    :key="`${item.plugin_id}:${item.index}`"
    type="button"
    class="button secondary"
    :title="`Plugin ${item.plugin_name}`"
    @click="open = item"
  >
    <Puzzle :size="16" />{{ item.title }}
  </button>
  <ModalDialog v-if="open" :title="open.title" wide @close="open = null">
    <PluginFrames
      :place="place"
      :context="context"
      :only="{ plugin_id: open.plugin_id, index: open.index }"
      bare
      @close="close"
    />
    <small class="muted">Do plugin {{ open.plugin_name }} cung cấp.</small>
  </ModalDialog>
</template>
