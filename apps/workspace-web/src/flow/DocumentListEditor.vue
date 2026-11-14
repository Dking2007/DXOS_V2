<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<!-- Names of the documents a step expects ("Tờ trình", "Báo giá"), one per line. They are shown on
     the dossier's process so everyone knows what this step needs; they are not checked file by file. -->
<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{ id: string; value?: string[] | null; hint?: string }>()
const emit = defineEmits<{ update: [names: string[]] }>()
const text = ref((props.value ?? []).join('\n'))
watch(
  () => props.value,
  (value) => {
    const incoming = (value ?? []).join('\n')
    if (incoming !== tidy(text.value).join('\n')) text.value = incoming
  },
)
function tidy(raw: string) {
  return raw
    .split('\n')
    .map((line) => line.trim().slice(0, 200))
    .filter(Boolean)
    .slice(0, 20)
}
</script>

<template>
  <div class="field">
    <label :for="id">Tài liệu cần có</label>
    <textarea
      :id="id"
      v-model="text"
      rows="3"
      placeholder="Mỗi dòng một tài liệu, ví dụ:&#10;Tờ trình&#10;Báo giá"
      @change="emit('update', tidy(text))"
    />
    <small>{{ hint ?? 'Hiện trong tab Quy trình của hồ sơ khi bấm vào bước này. Tối đa 20 tài liệu.' }}</small>
  </div>
</template>
