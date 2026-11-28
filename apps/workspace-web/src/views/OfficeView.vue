<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import { ArrowLeft, Maximize2, Minimize2, ShieldCheck } from 'lucide-vue-next'
import { api } from '../api'
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
// Full screen: the editor covers the whole window (sidebar, header and footer hidden) and, where the
// browser allows, the screen too. Only CSS changes, so the editor frame is never reloaded.
const page = ref<HTMLElement | null>(null)
const expanded = ref(false)
async function toggleExpanded() {
  expanded.value = !expanded.value
  if (expanded.value) {
    try {
      await page.value?.requestFullscreen?.()
    } catch {
      // Not allowed (or not supported): covering the window is enough.
    }
  } else if (document.fullscreenElement) {
    await document.exitFullscreen().catch(() => undefined)
  }
}
// Esc leaves the browser's full screen; leave the window-covering mode with it.
function onFullscreenChange() {
  if (!document.fullscreenElement && expanded.value) expanded.value = false
}
function onKey(event: KeyboardEvent) {
  if (event.key === 'Escape' && expanded.value && !document.fullscreenElement)
    expanded.value = false
}
watch(expanded, (on) =>
  document.documentElement.classList.toggle('office-expanded', on),
)
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
// Opened from a dossier: read through the dossier's rights, read-only.
const fromCase = typeof route.query.case === 'string' ? route.query.case : ''
async function open() {
  // A retry starts a fresh editor rather than stacking a second one on the old.
  editor?.destroyEditor()
  editor = undefined
  loading.value = true
  error.value = null
  try {
    const result = await api.request<{
      config: Record<string, unknown>
      document_server_url: string
      session_id: string
    }>(
      `/drive/files/${route.params.id}/office-sessions${fromCase ? `?case_id=${encodeURIComponent(fromCase)}` : ''}`,
      { method: 'POST' },
    )
    if (disposed) return
    sessionId.value = result.session_id
    await loadScript(result.document_server_url)
    if (disposed) return
    loading.value = false
    await new Promise((resolve) => requestAnimationFrame(resolve))
    // Left the page during that frame: an editor created now would never be destroyed.
    if (disposed) return
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
onMounted(() => {
  document.addEventListener('fullscreenchange', onFullscreenChange)
  document.addEventListener('keydown', onKey)
  void open()
})
onBeforeUnmount(() => {
  disposed = true
  editor?.destroyEditor()
  document.removeEventListener('fullscreenchange', onFullscreenChange)
  document.removeEventListener('keydown', onKey)
  document.documentElement.classList.remove('office-expanded')
  if (document.fullscreenElement)
    void document.exitFullscreen().catch(() => undefined)
})
</script>
<template>
  <section ref="page" class="office-page" :class="{ expanded }">
    <header class="office-toolbar">
      <RouterLink
        :to="fromCase ? `/cases/${fromCase}` : '/drive'"
        class="button ghost small"
        ><ArrowLeft :size="16" />{{
          fromCase ? 'Về hồ sơ' : 'Về kho tài liệu'
        }}</RouterLink
      ><span class="date-line office-state" role="status"
        ><ShieldCheck :size="16" />{{ editorState }}</span
      ><button
        v-if="!loading && !error"
        type="button"
        class="button ghost small"
        :aria-pressed="expanded"
        :title="expanded ? 'Thu nhỏ (Esc)' : 'Mở rộng toàn màn hình'"
        @click="toggleExpanded"
      >
        <component :is="expanded ? Minimize2 : Maximize2" :size="16" />{{
          expanded ? 'Thu nhỏ' : 'Toàn màn hình'
        }}
      </button>
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
    <div v-if="!loading && !error" class="notice warning office-note">
      <span
        >Sau khi sửa xong, hãy đóng trình soạn thảo và chờ vài giây để hệ thống
        lưu bản mới trước khi trình hồ sơ.</span
      >
    </div>
  </section>
</template>
<style scoped>
.office-note {
  border-radius: 0 0 8px 8px;
  font-size: 0.8125rem;
}
.office-state {
  margin-left: auto;
}
/* Covers the whole window, above the sidebar, header and the assistant button. */
.office-page.expanded {
  position: fixed;
  inset: 0;
  z-index: 1100;
  height: 100dvh;
  min-height: 0;
  padding: 0;
  background: var(--canvas);
}
.office-page.expanded .office-toolbar {
  border-radius: 0;
  border-width: 0 0 1px;
  padding: 6px 12px;
}
.office-page.expanded .office-frame {
  border: 0;
  min-height: 0;
}
.office-page.expanded .office-note {
  border-radius: 0;
}
</style>
<style>
/* The page behind must not scroll under the full-screen editor. */
html.office-expanded,
html.office-expanded body {
  overflow: hidden;
}
</style>
