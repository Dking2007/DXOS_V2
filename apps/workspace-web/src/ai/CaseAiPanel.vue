<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { ref } from 'vue'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { FileSearch, ListChecks, RefreshCw, Sparkles } from 'lucide-vue-next'
import { formatDate } from '@dx/web-shared/api.ts'
import { api } from '../api'
import { toast } from '../ui/toast'
import { useAi } from './useAi'

/** AI help on a dossier: a summary for whoever reads it, and for its author a check and read-and-fill. */
const props = defineProps<{
  caseId: string
  canEdit: boolean
  files: { id: string; name: string | null }[]
}>()
const { on } = useAi()
const queryClient = useQueryClient()
interface Summary {
  lines: string[]
  created_at: string
}
interface Issue {
  level: 'error' | 'warning' | 'info'
  message: string
  source: 'rule' | 'ai'
}
const summary = useQuery({
  queryKey: ['ai-case-summary', props.caseId],
  queryFn: () => api.request<{ summary: Summary | null }>(`/ai/cases/${props.caseId}/summary`),
  enabled: () => on('case_summary'),
})
const summarizing = ref(false)
const checking = ref(false)
const issues = ref<Issue[] | null>(null)
const reading = ref('')
const skipped = ref<{ key: string; reason: string }[]>([])
const LEVELS = { error: 'Cần sửa', warning: 'Nên xem', info: 'Lưu ý' }

async function summarize() {
  summarizing.value = true
  try {
    const result = await api.request<{ summary: Summary }>(`/ai/cases/${props.caseId}/summary`, { method: 'POST' })
    queryClient.setQueryData(['ai-case-summary', props.caseId], result)
  } catch (error) {
    toast.error(error)
  } finally {
    summarizing.value = false
  }
}
async function check() {
  checking.value = true
  try {
    issues.value = (await api.request<{ issues: Issue[] }>(`/ai/cases/${props.caseId}/check`, { method: 'POST' })).issues
  } catch (error) {
    toast.error(error)
  } finally {
    checking.value = false
  }
}
async function read(fileId: string) {
  reading.value = fileId
  skipped.value = []
  try {
    const result = await api.request<{ created: unknown[]; skipped: { key: string; reason: string }[] }>(
      `/ai/cases/${props.caseId}/extract`,
      { method: 'POST', body: JSON.stringify({ file_id: fileId }) },
    )
    skipped.value = result.skipped
    await queryClient.invalidateQueries({ queryKey: ['field-evidence', props.caseId] })
    if (result.created.length)
      toast.success(`AI đề xuất ${result.created.length} giá trị. Xem và xác nhận ở mục “Đối chiếu với tài liệu gốc”.`)
    else toast.error('AI chưa tìm được giá trị nào có căn cứ rõ trong tài liệu này.')
  } catch (error) {
    toast.error(error)
  } finally {
    reading.value = ''
  }
}
</script>
<template>
  <section v-if="on('case_summary')" class="ai-card" aria-live="polite">
    <header>
      <span class="ai-title"><Sparkles :size="16" />Tóm tắt hồ sơ</span>
      <button class="button secondary small ai-action" :disabled="summarizing" @click="summarize">
        <RefreshCw v-if="summary.data.value?.summary" :size="14" /><Sparkles v-else :size="14" />{{
          summarizing ? 'Đang tóm tắt…' : summary.data.value?.summary ? 'Tóm tắt lại' : 'Tóm tắt bằng AI'
        }}
      </button>
    </header>
    <ul v-if="summary.data.value?.summary">
      <li v-for="(line, index) in summary.data.value.summary.lines" :key="index">{{ line }}</li>
    </ul>
    <p v-else class="muted">Bấm để AI tóm tắt nội dung xin duyệt, số tiền, tài liệu kèm và ý kiến các bước trước.</p>
    <p v-if="summary.data.value?.summary" class="ai-note">
      Do AI viết lúc {{ formatDate(summary.data.value.summary.created_at, true) }} từ nội dung hồ sơ; đối chiếu với hồ sơ
      trước khi quyết định.
    </p>
  </section>

  <section v-if="canEdit && (on('case_check') || (on('case_extract') && files.length))" class="ai-card">
    <header><span class="ai-title"><Sparkles :size="16" />AI hỗ trợ lập hồ sơ</span></header>
    <div v-if="on('case_extract') && files.length" class="stack" style="gap: 6px">
      <small class="muted">Đọc tài liệu đính kèm và đề xuất giá trị cho các trường, kèm trang và câu trích để bạn xác nhận.</small>
      <div class="ai-chips">
        <button
          v-for="file in files"
          :key="file.id"
          class="button secondary small ai-action"
          :disabled="!!reading"
          @click="read(file.id)"
        >
          <FileSearch :size="14" />{{ reading === file.id ? 'Đang đọc…' : `Đọc “${file.name}”` }}
        </button>
      </div>
      <ul v-if="skipped.length" class="ai-note">
        <li v-for="item in skipped" :key="item.key + item.reason">Bỏ qua {{ item.key }}: {{ item.reason }}</li>
      </ul>
    </div>
    <div v-if="on('case_check')" style="margin-top: 10px">
      <button class="button secondary small ai-action" :disabled="checking" @click="check">
        <ListChecks :size="14" />{{ checking ? 'Đang soát…' : 'Soát hồ sơ trước khi trình' }}
      </button>
      <div v-if="issues" style="margin-top: 8px">
        <p v-if="!issues.length">Không thấy điểm nào đáng lưu ý.</p>
        <div v-for="(issue, index) in issues" :key="index" class="ai-issue">
          <span class="level" :class="issue.level">{{ LEVELS[issue.level] }}</span>
          <span>{{ issue.message }}<small v-if="issue.source === 'ai'" class="muted"> · AI</small></span>
        </div>
      </div>
    </div>
  </section>
</template>
