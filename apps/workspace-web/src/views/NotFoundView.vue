<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { RouterLink } from 'vue-router'
import { ArrowLeft, FileQuestion } from 'lucide-vue-next'
</script>
<template>
  <div class="card state-panel">
    <FileQuestion :size="40" />
    <h1>Không tìm thấy trang</h1>
    <p>Đường dẫn này không tồn tại hoặc đã được thay đổi.</p>
    <RouterLink to="/home" class="button secondary"
      ><ArrowLeft :size="17" />Về không gian làm việc</RouterLink
    >
  </div>
</template>
