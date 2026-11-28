<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef } from 'vue'
import {
  ChevronLeft,
  ChevronRight,
  Download,
  FileQuestion,
  LoaderCircle,
  Maximize2,
  X,
  ZoomIn,
  ZoomOut,
} from 'lucide-vue-next'
import type { PDFDocumentProxy } from 'pdfjs-dist'
import { errorText } from '@dx/web-shared/api.ts'
import { previewKind, TEXT_PREVIEW_LIMIT } from '../ui/preview'
import { piiSummary } from '../ui/pii'
import { api } from '../api'

const props = defineProps<{
  name: string
  mime?: string | null
  /** Drive file id; when given, the file's text is checked for personal data. */
  fileId?: string
  /** Resolves to a URL the browser can fetch (a short-lived download link). */
  source: () => Promise<string>
  /** Opens the normal download; omitted when downloading is not offered. */
  download?: () => void
}>()
const emit = defineEmits<{ close: [] }>()

const kind = computed(() => previewKind(props.name, props.mime))
const loading = ref(true)
const error = ref('')
const objectUrl = ref('')
const text = ref('')
const truncated = ref(false)
const pdf = shallowRef<PDFDocumentProxy | null>(null)
const pageCount = ref(0)
const page = ref(1)
const zoom = ref(1)
const fitWidth = ref(true)
const pagesEl = ref<HTMLElement>()
const dialog = ref<HTMLDialogElement>()
let previous: Element | null = null
let renderToken = 0
/** Closed while the file was still loading: whatever arrives late is released, not shown. */
let disposed = false
const abort = new AbortController()
const piiWarning = ref('')
const maskedText = ref<string | null>(null)

// A hint only: when the check fails or finds nothing, the preview stays as it was.
async function checkPii() {
  if (!props.fileId) return
  try {
    const report = await api.request<{ counts: Record<string, number> }>(`/drive/files/${props.fileId}/pii`)
    if (!disposed) piiWarning.value = piiSummary(report.counts)
  } catch {
    /* no warning */
  }
}
async function showMasked() {
  try {
    const report = await api.request<{ redacted_text?: string }>(`/drive/files/${props.fileId}/pii?redacted=true`)
    if (!disposed) maskedText.value = report.redacted_text ?? ''
  } catch (cause) {
    if (!disposed) error.value = errorText(cause)
  }
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const url = await props.source()
    if (disposed) return
    // fetch() reads the bytes whatever Content-Disposition says; nothing is served
    // inline from our origin, and PDFs are drawn by pdf.js rather than the browser.
    const response = await fetch(url, { credentials: 'same-origin', signal: abort.signal })
    if (!response.ok) throw new Error('Không tải được tệp. Liên kết có thể đã hết hạn, hãy mở lại.')
    const blob = await response.blob()
    if (disposed) return
    if (kind.value === 'text') {
      truncated.value = blob.size > TEXT_PREVIEW_LIMIT
      text.value = await blob.slice(0, TEXT_PREVIEW_LIMIT).text()
    } else if (kind.value === 'pdf') {
      const pdfjs = await import('./pdf')
      const doc = await pdfjs.openPdf(await blob.arrayBuffer())
      // The dialog closed while pdf.js parsed: free the document and its worker-side state.
      if (disposed) {
        void doc.destroy()
        return
      }
      void pdf.value?.destroy()
      pdf.value = doc
      pageCount.value = pdf.value.numPages
      loading.value = false
      await nextTick()
      await renderPdf()
    } else {
      const type = kind.value === 'image' ? blob.type || 'image/png' : blob.type
      if (objectUrl.value) URL.revokeObjectURL(objectUrl.value)
      objectUrl.value = URL.createObjectURL(new Blob([blob], { type }))
    }
  } catch (cause) {
    if (disposed) return
    error.value = errorText(cause)
  } finally {
    loading.value = false
  }
}

async function renderPdf() {
  const doc = pdf.value
  const host = pagesEl.value
  if (!doc || !host) return
  const token = ++renderToken
  host.replaceChildren()
  const available = Math.max(320, host.clientWidth - 32)
  for (let number = 1; number <= doc.numPages; number++) {
    const current = await doc.getPage(number)
    if (token !== renderToken) return
    const base = current.getViewport({ scale: 1 })
    const scale = fitWidth.value ? available / base.width : zoom.value
    const viewport = current.getViewport({ scale: scale * window.devicePixelRatio })
    const canvas = document.createElement('canvas')
    canvas.width = Math.floor(viewport.width)
    canvas.height = Math.floor(viewport.height)
    canvas.style.width = `${Math.floor(viewport.width / window.devicePixelRatio)}px`
    canvas.dataset.page = String(number)
    canvas.setAttribute('role', 'img')
    canvas.setAttribute('aria-label', `Trang ${number} / ${doc.numPages}`)
    host.append(canvas)
    await current.render({ canvasContext: canvas.getContext('2d')!, viewport }).promise
    if (token !== renderToken) return
    if (number === 1 && fitWidth.value) zoom.value = Math.round(scale * 100) / 100
  }
}

function setZoom(value: number) {
  fitWidth.value = false
  zoom.value = Math.min(4, Math.max(0.25, Math.round(value * 100) / 100))
  void renderPdf()
}
function fit() {
  fitWidth.value = true
  void renderPdf()
}
function goTo(number: number) {
  page.value = Math.min(Math.max(1, number), pageCount.value)
  pagesEl.value?.querySelector(`[data-page="${page.value}"]`)?.scrollIntoView({ block: 'start' })
}
// Reading every page's position forces layout, so do it at most once per frame while scrolling.
let scrollFrame = 0
function onScroll() {
  if (!scrollFrame) scrollFrame = requestAnimationFrame(updatePage)
}
function updatePage() {
  scrollFrame = 0
  const host = pagesEl.value
  if (!host) return
  const top = host.getBoundingClientRect().top
  let current = 1
  for (const canvas of host.querySelectorAll<HTMLCanvasElement>('canvas'))
    if (canvas.getBoundingClientRect().top - top < host.clientHeight / 2) current = Number(canvas.dataset.page)
  page.value = current
}
function onKey(event: KeyboardEvent) {
  if (kind.value !== 'pdf' || event.target instanceof HTMLInputElement) return
  if (event.key === 'ArrowRight' || event.key === 'PageDown') goTo(page.value + 1)
  else if (event.key === 'ArrowLeft' || event.key === 'PageUp') goTo(page.value - 1)
  else if (event.key === '+' || event.key === '=') setZoom(zoom.value + 0.25)
  else if (event.key === '-') setZoom(zoom.value - 0.25)
  else return
  event.preventDefault()
}
let resizeTimer = 0
function onResize() {
  if (!fitWidth.value) return
  window.clearTimeout(resizeTimer)
  resizeTimer = window.setTimeout(() => void renderPdf(), 200)
}

onMounted(async () => {
  previous = document.activeElement
  window.addEventListener('resize', onResize)
  await nextTick()
  if (disposed) return
  dialog.value?.showModal()
  void checkPii()
  if (kind.value) await load()
  else loading.value = false
})
onBeforeUnmount(() => {
  disposed = true
  renderToken++
  abort.abort()
  window.clearTimeout(resizeTimer)
  cancelAnimationFrame(scrollFrame)
  window.removeEventListener('resize', onResize)
  if (objectUrl.value) URL.revokeObjectURL(objectUrl.value)
  void pdf.value?.destroy()
  if (previous instanceof HTMLElement) previous.focus()
})
</script>
<template>
  <dialog
    ref="dialog"
    class="file-preview"
    :aria-label="`Xem ${name}`"
    @cancel.prevent="emit('close')"
    @keydown="onKey"
  >
    <header class="preview-bar">
      <strong class="preview-name" :title="name">{{ name }}</strong>
      <div v-if="kind === 'pdf' && pageCount" class="preview-tools" role="group" aria-label="Điều khiển PDF">
        <button class="icon-button" type="button" aria-label="Trang trước" title="Trang trước (←)" :disabled="page <= 1" @click="goTo(page - 1)">
          <ChevronLeft :size="18" />
        </button>
        <label class="preview-page"
          ><input
            type="number"
            min="1"
            :max="pageCount"
            :value="page"
            aria-label="Đến trang"
            @change="goTo(Number(($event.target as HTMLInputElement).value))"
          />/ {{ pageCount }}</label
        >
        <button class="icon-button" type="button" aria-label="Trang sau" title="Trang sau (→)" :disabled="page >= pageCount" @click="goTo(page + 1)">
          <ChevronRight :size="18" />
        </button>
        <span class="preview-divider" />
        <button class="icon-button" type="button" aria-label="Thu nhỏ" title="Thu nhỏ (−)" :disabled="zoom <= 0.25" @click="setZoom(zoom - 0.25)"><ZoomOut :size="18" /></button>
        <span class="preview-zoom">{{ Math.round(zoom * 100) }}%</span>
        <button class="icon-button" type="button" aria-label="Phóng to" title="Phóng to (+)" :disabled="zoom >= 4" @click="setZoom(zoom + 0.25)"><ZoomIn :size="18" /></button>
        <button class="icon-button" type="button" aria-label="Vừa khung" title="Vừa khung" :class="{ active: fitWidth }" :aria-pressed="fitWidth" @click="fit">
          <Maximize2 :size="17" />
        </button>
      </div>
      <div class="preview-actions">
        <button v-if="download" class="button secondary small" type="button" @click="download">
          <Download :size="15" />Tải về
        </button>
        <button class="icon-button" type="button" aria-label="Đóng" title="Đóng (Esc)" @click="emit('close')"><X :size="20" /></button>
      </div>
    </header>
    <div v-if="piiWarning" class="notice warning" role="status">
      Tệp có thể chứa dữ liệu cá nhân: {{ piiWarning }}.
      <button class="button secondary small" type="button" :aria-pressed="maskedText !== null" @click="maskedText === null ? showMasked() : (maskedText = null)">
        {{ maskedText === null ? 'Xem bản đã che' : 'Ẩn bản đã che' }}
      </button>
    </div>
    <div v-if="maskedText !== null" class="preview-body text">
      <div class="preview-text"><pre>{{ maskedText || 'Không có nội dung chữ.' }}</pre></div>
    </div>
    <div v-show="maskedText === null" class="preview-body" :class="kind ?? 'none'">
      <div v-if="loading" class="preview-state" role="status">
        <LoaderCircle class="spin" :size="28" /><span>Đang mở tệp…</span>
      </div>
      <div v-else-if="error" class="preview-state" role="alert">
        <strong>{{ error }}</strong>
        <button class="button secondary small" type="button" @click="load">Thử lại</button>
      </div>
      <div v-else-if="!kind" class="preview-state">
        <FileQuestion :size="34" />
        <strong>Chưa xem trước được loại tệp này</strong>
        <span>Tải về để mở bằng phần mềm trên máy.</span>
        <button v-if="download" class="button small" type="button" @click="download"><Download :size="15" />Tải về</button>
      </div>
      <img v-else-if="kind === 'image'" :src="objectUrl" :alt="name" class="preview-image" />
      <video v-else-if="kind === 'video'" :src="objectUrl" controls class="preview-media" />
      <audio v-else-if="kind === 'audio'" :src="objectUrl" controls class="preview-audio" />
      <div v-else-if="kind === 'text'" class="preview-text">
        <p v-if="truncated" class="notice warning">Tệp lớn, chỉ hiện 512 KB đầu tiên. Tải về để xem đầy đủ.</p>
        <pre>{{ text }}</pre>
      </div>
      <div v-show="kind === 'pdf' && !loading && !error" ref="pagesEl" class="preview-pages" @scroll.passive="onScroll" />
    </div>
  </dialog>
</template>
