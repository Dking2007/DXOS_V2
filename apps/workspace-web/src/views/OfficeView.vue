<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import { ArrowLeft, ShieldCheck } from 'lucide-vue-next'
import { api } from '../api'
import { errorText } from '@dx/web-shared/api.ts'
import StatePanel from '@dx/web-shared/components/StatePanel.vue'
interface Editor {
  destroyEditor(): void
}
declare global {
  interface Window {
    DocsAPI?: {
      DocEditor: new (id: string, config: Record<string, unknown>) => Editor
    }
  }
}
const route = useRoute()
const loading = ref(true)
const error = ref<unknown>(null)
const sessionId = ref('')
const editorState = ref('Đang mở tài liệu…')
let editor: Editor | undefined
let disposed = false
async function loadScript(url: string) {
  if (window.DocsAPI) return
  const scriptUrl = `${url.replace(/\/$/, '')}/web-apps/apps/api/documents/api.js`
  if (!/^https?:\/\//.test(scriptUrl) && !scriptUrl.startsWith('/'))
    throw new Error('Địa chỉ trình soạn thảo không hợp lệ.')
  await new Promise<void>((resolve, reject) => {
    const script = document.createElement('script')
    script.src = scriptUrl
    script.onload = () => resolve()
    script.onerror = () => {
      script.remove()
      reject(
        new Error(
          'Không tải được ONLYOFFICE. Kiểm tra Document Server và địa chỉ truy cập.',
        ),
      )
    }
    document.head.append(script)
  })
}
async function open() {
  loading.value = true
  error.value = null
  try {
    const result = await api.request<{
      config: Record<string, unknown>
      document_server_url: string
      session_id: string
    }>(`/drive/files/${route.params.id}/office-sessions`, { method: 'POST' })
    sessionId.value = result.session_id
    await loadScript(result.document_server_url)
    if (disposed) return
    loading.value = false
    await new Promise((resolve) => requestAnimationFrame(resolve))
    if (!window.DocsAPI)
      throw new Error(
        'Trình soạn thảo chưa khởi tạo. Tải lại trang để thử lại.',
      )
    // ONLYOFFICE verifies the signed config. Do not mutate document permissions or identity here.
    editor = new window.DocsAPI.DocEditor('document-editor', {
      ...result.config,
      height: '100%',
      width: '100%',
      events: {
        onDocumentReady: () => {
          editorState.value =
            'Đang mở phiên chỉnh sửa · chờ đóng phiên để chốt bản lưu'
        },
        onDocumentStateChange: (event: { data: boolean }) => {
          editorState.value = event.data
            ? 'Có thay đổi trong trình soạn thảo · chưa xác nhận lưu về hệ thống'
            : 'Trình soạn thảo đã gửi thay đổi · cần chờ hệ thống xác nhận bản lưu cuối'
        },
        onError: (event: { data?: { errorDescription?: string } }) => {
          error.value = new Error(
            event.data?.errorDescription ||
              'Trình soạn thảo báo lỗi. Chưa xác nhận tài liệu đã lưu.',
          )
        },
      },
    })
  } catch (cause) {
    error.value = cause
    loading.value = false
  }
}
onMounted(open)
onBeforeUnmount(() => {
  disposed = true
  editor?.destroyEditor()
})
</script>
<template>
  <section class="office-page">
    <header class="office-toolbar">
      <RouterLink to="/drive" class="button ghost small"
        ><ArrowLeft :size="16" />Về kho tài liệu</RouterLink
      ><span class="date-line" role="status"
        ><ShieldCheck :size="16" />{{ editorState }}</span
      >
    </header>
    <StatePanel
      v-if="loading || error"
      :loading="loading"
      :error="error"
      @retry="open"
    />
    <div v-show="!loading && !error" class="office-frame">
      <div id="document-editor" />
    </div>
    <div
      v-if="!loading"
      class="notice warning"
      style="border-radius: 0 0 8px 8px; font-size: 12px"
    >
      <span
        >Đóng trình soạn thảo và đợi phiên lưu hoàn tất trước khi trình hồ sơ.
        Trạng thái lưu trong editor không thay thế xác nhận lưu bền vững của hệ
        thống.<span v-if="error"> {{ errorText(error) }}</span
        ><span
          v-if="sessionId"
          class="mono"
          style="display: block; margin-top: 4px"
          >Phiên {{ sessionId }}</span
        ></span
      >
    </div>
  </section>
</template>
