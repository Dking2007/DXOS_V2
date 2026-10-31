<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { ref } from 'vue'
import { Sparkles } from 'lucide-vue-next'
import ModalDialog from '@dx/web-shared/components/ModalDialog.vue'
import { errorText } from '@dx/web-shared/api.ts'
import { api } from '../api'
import { confirmDiscard } from '../ui/unsaved'

/** A few points in, an administrative document laid out per Decree 30 out, saved in the open folder. */
const props = defineProps<{ folderId: string | null }>()
const emit = defineEmits<{ close: []; created: [file: { id: string; name: string }] }>()
const KINDS = [
  { value: 'to_trinh', label: 'Tờ trình' },
  { value: 'cong_van', label: 'Công văn' },
  { value: 'thong_bao', label: 'Thông báo' },
  { value: 'ke_hoach', label: 'Kế hoạch' },
  { value: 'bao_cao', label: 'Báo cáo' },
  { value: 'giay_moi', label: 'Giấy mời' },
]
const kind = ref('to_trinh')
const points = ref('')
const recipients = ref('')
const signerTitle = ref('')
const signerName = ref('')
const busy = ref(false)
const error = ref('')
async function submit() {
  busy.value = true
  error.value = ''
  try {
    const file = await api.request<{ id: string; name: string }>('/ai/documents/draft', {
      method: 'POST',
      body: JSON.stringify({
        kind: kind.value,
        points: points.value,
        recipients: recipients.value,
        signer_title: signerTitle.value,
        signer_name: signerName.value,
        folder_id: props.folderId,
      }),
    })
    emit('created', file)
  } catch (cause) {
    error.value = errorText(cause)
  } finally {
    busy.value = false
  }
}
function close() {
  if (!busy.value && confirmDiscard(!!points.value.trim())) emit('close')
}
</script>
<template>
  <ModalDialog title="Soạn văn bản hành chính bằng AI" wide @close="close">
    <form class="stack" @submit.prevent="submit">
      <div v-if="error" class="notice error" role="alert">{{ error }}</div>
      <div class="form-grid">
        <div class="field">
          <label for="draft-kind">Loại văn bản</label>
          <select id="draft-kind" v-model="kind">
            <option v-for="item in KINDS" :key="item.value" :value="item.value">{{ item.label }}</option>
          </select>
        </div>
        <div class="field">
          <label for="draft-to">Kính gửi (không bắt buộc)</label>
          <input id="draft-to" v-model="recipients" maxlength="500" placeholder="Ví dụ: Giám đốc" />
        </div>
      </div>
      <div class="field">
        <label for="draft-points">Các ý chính<span class="required"> *</span></label>
        <textarea
          id="draft-points"
          v-model="points"
          rows="6"
          maxlength="6000"
          required
          placeholder="Ví dụ: Xin mua 01 máy chiếu cho phòng họp tầng 3; máy cũ hỏng từ tháng 9; báo giá 48,5 triệu đồng; đề nghị duyệt trong tháng 11."
        />
      </div>
      <div class="form-grid">
        <div class="field">
          <label for="draft-signer-title">Chức vụ người ký</label>
          <input id="draft-signer-title" v-model="signerTitle" maxlength="120" placeholder="TRƯỞNG PHÒNG" />
        </div>
        <div class="field">
          <label for="draft-signer">Họ tên người ký</label>
          <input id="draft-signer" v-model="signerName" maxlength="120" />
        </div>
      </div>
      <div class="notice">
        Văn bản được trình bày theo Nghị định 30/2020/NĐ-CP (khổ A4, lề, phông Times New Roman, quốc hiệu, tiêu ngữ)
        và lưu thành tệp Word trong thư mục đang mở. Mở bằng ONLYOFFICE để sửa, ghi số và kiểm tra thể thức.
      </div>
      <div class="form-actions">
        <button type="button" class="button secondary" :disabled="busy" @click="close">Hủy</button>
        <button class="button ai-action" :disabled="busy || points.trim().length < 5">
          <Sparkles :size="16" />{{ busy ? 'AI đang soạn…' : 'Soạn văn bản' }}
        </button>
      </div>
    </form>
  </ModalDialog>
</template>
