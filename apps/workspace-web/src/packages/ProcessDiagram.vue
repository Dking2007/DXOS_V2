<script setup lang="ts">
import { FilePlus2, Flag, GitBranch, Paperclip, UserCheck } from 'lucide-vue-next'
import type { ApprovalStep, FormField } from '@dx/web-shared/types.ts'
import { conditionText, formatValue, resolverText } from './model'
import type { RoutingEvidence } from './model'
const props = defineProps<{
  steps: ApprovalStep[]
  fields: FormField[]
  requiredFiles: number
  userName: (id: string) => string
  /** When present (from a preview), shows which steps applied to that sample case. */
  evidence?: RoutingEvidence[] | null
}>()
function evidenceAt(index: number) {
  return props.evidence?.[index] ?? null
}
</script>
<template>
  <ol class="process-diagram" :class="{ traced: !!evidence }" aria-label="Sơ đồ quy trình duyệt">
    <li class="process-stop start">
      <span class="process-icon"><FilePlus2 :size="18" /></span>
      <div>
        <strong>Người tạo trình hồ sơ</strong>
        <small v-if="requiredFiles"><Paperclip :size="12" /> Kèm tối thiểu {{ requiredFiles }} tài liệu</small>
        <small v-else>Không bắt buộc tài liệu</small>
      </div>
    </li>
    <li
      v-for="(step, index) in steps"
      :key="index"
      class="process-stop step"
      :class="{
        conditional: !!step.condition,
        selected: evidenceAt(index)?.selected,
        skipped: evidence && !evidenceAt(index)?.selected,
      }"
    >
      <span class="process-index">{{ index + 1 }}</span>
      <div>
        <strong>{{ step.label }}</strong>
        <small><UserCheck :size="12" /> {{ resolverText(step, userName) }}</small>
        <span v-if="step.condition" class="process-condition"
          ><GitBranch :size="12" /> Chỉ khi {{ conditionText(step.condition, fields) }}</span
        >
        <span v-else class="process-condition always">Luôn áp dụng</span>
        <span v-if="evidenceAt(index)" class="process-trace">
          <template v-if="evidenceAt(index)!.selected"
            >✓ Áp dụng · người duyệt: {{ evidenceAt(index)!.recipient ?? '—' }}</template
          >
          <template v-else
            >Bỏ qua · giá trị hồ sơ: {{ formatValue(evidenceAt(index)!.evaluated_value) }}</template
          >
        </span>
      </div>
    </li>
    <li class="process-stop end">
      <span class="process-icon"><Flag :size="18" /></span>
      <div>
        <strong>Hoàn tất</strong>
        <small>Duyệt hết các bước áp dụng. Trả lại hoặc từ chối sẽ dừng quy trình.</small>
      </div>
    </li>
  </ol>
</template>
