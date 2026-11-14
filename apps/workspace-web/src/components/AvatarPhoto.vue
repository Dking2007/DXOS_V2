<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<!-- The person's photo laid over an initials circle; the initials stay when there is no photo or it fails. -->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { usePhotos } from '../ui/people'

const props = defineProps<{ userId?: string | null; url?: string | null }>()
const photoOf = usePhotos()
const src = computed(() => props.url ?? photoOf(props.userId))
const failed = ref(false)
watch(src, () => (failed.value = false))
</script>

<template>
  <img
    v-if="src && !failed"
    class="avatar-photo"
    :src="src"
    alt=""
    loading="lazy"
    @error="failed = true"
  />
</template>
