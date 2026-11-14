<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<!-- A connected plugin's own page, opened from its entry in the sidebar, or its administration page
     (Quản trị › Plugin). -->
<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import PluginFrames from '../components/plugins/PluginFrames.vue'

const props = withDefaults(defineProps<{ place?: 'page' | 'admin.page' }>(), { place: 'page' })
const route = useRoute()
const only = computed(() => ({ plugin_id: String(route.params.pluginId), index: Number(route.params.index) }))
</script>
<template>
  <h1 class="sr-only">Ứng dụng của plugin</h1>
  <PluginFrames :key="`${only.plugin_id}:${only.index}`" :place="props.place" :only="only" bare />
</template>
