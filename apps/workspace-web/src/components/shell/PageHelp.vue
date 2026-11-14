<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { CircleAlert } from 'lucide-vue-next'
import ModalDialog from '@dx/web-shared/components/ModalDialog.vue'
import { HELP } from '../../ui/help'

/** The (!) beside the page name: how to use the screen the person is on. */
const route = useRoute()
const open = ref(false)
const pattern = computed(() => route.matched[route.matched.length - 1]?.path ?? route.path)
const topic = computed(() => HELP[pattern.value])
const title = computed(() => String(route.meta.title ?? ''))
</script>
<template>
  <button
    v-if="topic"
    class="icon-button page-help"
    type="button"
    :aria-label="`Hướng dẫn sử dụng ${title}`"
    title="Hướng dẫn sử dụng"
    @click="open = true"
  >
    <CircleAlert :size="18" aria-hidden="true" />
  </button>
  <ModalDialog v-if="open && topic" :title="`Hướng dẫn: ${title}`" @close="open = false">
    <div class="page-help-body">
      <p>{{ topic.purpose }}</p>
      <h3>Cách dùng</h3>
      <ol>
        <li v-for="step in topic.steps" :key="step">{{ step }}</li>
      </ol>
      <template v-if="topic.tips.length">
        <h3>Lưu ý</h3>
        <ul>
          <li v-for="tip in topic.tips" :key="tip">{{ tip }}</li>
        </ul>
      </template>
    </div>
  </ModalDialog>
</template>
<style scoped>
.page-help {
  width: 32px;
  height: 32px;
  margin-left: -6px;
  color: var(--muted);
}
.page-help:hover {
  color: var(--teal-ink);
}
/* The dialog opens from inside the top bar, whose title must not wrap; the help text must. */
.page-help-body {
  display: grid;
  gap: 10px;
  line-height: 1.55;
  white-space: normal;
  overflow-wrap: anywhere;
}
.page-help-body p {
  margin: 0;
}
.page-help-body h3 {
  margin: 8px 0 0;
  font-size: 15px;
}
.page-help-body ol,
.page-help-body ul {
  margin: 0;
  padding-left: 22px;
  display: grid;
  gap: 6px;
}
@media (pointer: coarse) {
  .page-help {
    width: 40px;
    height: 40px;
  }
}
</style>
