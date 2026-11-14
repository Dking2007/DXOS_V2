<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<!-- A connected plugin's own page, opened from its entry in the sidebar. -->
<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import PluginFrames from '../components/plugins/PluginFrames.vue'

const route = useRoute()
const only = computed(() => ({ plugin_id: String(route.params.pluginId), index: Number(route.params.index) }))
</script>
<template>
  <h1 class="sr-only">Ứng dụng của plugin</h1>
  <PluginFrames :key="`${only.plugin_id}:${only.index}`" place="page" :only="only" bare />
</template>
