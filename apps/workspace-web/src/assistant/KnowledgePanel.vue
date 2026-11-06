<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { EyeOff, FileUp, PackageOpen, Pencil, Plus, Search, Trash2, Workflow } from 'lucide-vue-next'
import type { AssistantAdmin, AssistantArticle } from '@dx/web-shared/types.ts'
import type { Page } from '@dx/web-shared/api.ts'
import { errorText, formatDate } from '@dx/web-shared/api.ts'
import ModalDialog from '@dx/web-shared/components/ModalDialog.vue'
import StatePanel from '@dx/web-shared/components/StatePanel.vue'
import { api } from '../api'
import { toast } from '../ui/toast'
import { confirmDiscard } from '../ui/unsaved'

defineProps<{ categories: AssistantAdmin['categories'] }>()
const emit = defineEmits<{ changed: [] }>()
const queryClient = useQueryClient()

const q = ref('')
const debounced = ref('')
let timer = 0
watch(q, (value) => {
  window.clearTimeout(timer)
  timer = window.setTimeout(() => (debounced.value = value.trim()), 250)
})
const category = ref('')
const list = useQuery({
  queryKey: computed(() => ['assistant-articles', debounced.value, category.value]),
  queryFn: () =>
    api.request<Page<AssistantArticle>>(
      `/assistant/articles?limit=200${debounced.value ? `&q=${encodeURIComponent(debounced.value)}` : ''}${category.value ? `&category=${category.value}` : ''}`,
    ),
})

async function refresh() {
  await queryClient.invalidateQueries({ queryKey: ['assistant-articles'] })
  emit('changed')
}

// ---- Editor ----
const editing = ref<AssistantArticle | null>(null)
const editorOpen = ref(false)
const title = ref('')
const kind = ref<AssistantArticle['category']>('guide')
const body = ref('')
const published = ref(true)
const busy = ref(false)
const error = ref('')
const opened = ref('')
const state = () => JSON.stringify([title.value, kind.value, body.value, published.value])
function openNew() {
  editing.value = null
  title.value = ''
  kind.value = 'guide'
  body.value = ''
  published.value = true
  error.value = ''
  editorOpen.value = true
  opened.value = state()
}
async function openEdit(item: AssistantArticle) {
  try {
    const full = await api.request<AssistantArticle>(`/assistant/articles/${item.id}`)
    editing.value = full
    title.value = full.title
    kind.value = full.category
    body.value = full.body ?? ''
    published.value = full.published
    error.value = ''
    editorOpen.value = true
    opened.value = state()
  } catch (cause) {
    toast.error(cause)
  }
}
function closeEditor() {
  if (!busy.value && confirmDiscard(state() !== opened.value)) editorOpen.value = false
}
async function importFile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  if (file.size > 200_000) {
    toast.error('Tệp lớn hơn 200 KB. Hãy chia thành nhiều bài nhỏ theo từng chủ đề.')
    return
  }
  const text = await file.text()
  body.value = body.value ? `${body.value}\n\n${text}` : text
  if (!title.value) title.value = file.name.replace(/\.(md|txt)$/i, '').replace(/[-_]+/g, ' ')
}
async function saveArticle() {
  busy.value = true
  error.value = ''
  try {
    const payload = { title: title.value, category: kind.value, body: body.value, published: published.value }
    if (editing.value)
      await api.request(`/assistant/articles/${editing.value.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ ...payload, expected_revision: editing.value.revision }),
      })
    else await api.request('/assistant/articles', { method: 'POST', body: JSON.stringify(payload) })
    toast.success(editing.value ? 'Đã lưu bài kiến thức' : 'Đã thêm bài kiến thức')
    editorOpen.value = false
    await refresh()
  } catch (cause) {
    error.value = errorText(cause)
  } finally {
    busy.value = false
  }
}
async function remove(item: AssistantArticle) {
  if (!window.confirm(`Xóa bài “${item.title}”? Trợ lý sẽ không dùng bài này nữa.`)) return
  try {
    await api.request(`/assistant/articles/${item.id}`, { method: 'DELETE' })
    toast.success('Đã xóa bài kiến thức')
    await refresh()
  } catch (cause) {
    toast.error(cause)
  }
}

// ---- Business packages ----
interface PackageSource {
  package_id: string
  name: string
  version_no: number
  article_id: string | null
  imported_at: string | null
}
const packagesOpen = ref(false)
const packages = useQuery({
  queryKey: ['assistant-package-sources'],
  queryFn: () => api.request<{ items: PackageSource[] }>('/assistant/package-sources'),
  enabled: packagesOpen,
})
const importing = ref('')
async function importPackage(item: PackageSource) {
  importing.value = item.package_id
  try {
    await api.request('/assistant/articles/from-package', {
      method: 'POST',
      body: JSON.stringify({ package_id: item.package_id }),
    })
    toast.success(item.article_id ? `Đã cập nhật quy trình “${item.name}”` : `Đã thêm quy trình “${item.name}”`)
    await packages.refetch()
    await refresh()
  } catch (cause) {
    toast.error(cause)
  } finally {
    importing.value = ''
  }
}

// ---- Search preview ----
const probe = ref('')
const probing = ref(false)
const probeResult = ref<{ article_id: string; title: string; text: string }[] | null>(null)
async function runProbe() {
  if (!probe.value.trim()) return
  probing.value = true
  try {
    probeResult.value = (
      await api.request<{ items: { article_id: string; title: string; text: string }[] }>(
        '/assistant/search-preview',
        { method: 'POST', body: JSON.stringify({ q: probe.value }) },
      )
    ).items
  } catch (cause) {
    toast.error(cause)
  } finally {
    probing.value = false
  }
}
</script>
<template>
  <div class="split">
    <section class="card">
      <header class="card-header knowledge-head">
        <div>
          <h2>Kiến thức của trợ lý</h2>
          <p class="muted" style="font-size: 14px; margin-top: 4px">
            Mỗi bài nên nói về một chủ đề. Trợ lý tìm đoạn liên quan nhất cho từng câu hỏi.
          </p>
        </div>
        <div class="inline-actions">
          <button class="button secondary" type="button" @click="packagesOpen = true">
            <PackageOpen :size="16" />Nhập từ quy trình
          </button>
          <button class="button" type="button" @click="openNew"><Plus :size="16" />Viết bài</button>
        </div>
      </header>
      <div class="knowledge-filters">
        <label class="search-box"
          ><Search :size="16" /><input v-model="q" type="search" placeholder="Tìm trong kiến thức…" aria-label="Tìm bài kiến thức"
        /></label>
        <select v-model="category" aria-label="Loại bài" class="compact-select">
          <option value="">Mọi loại</option>
          <option v-for="item in categories" :key="item.key" :value="item.key">{{ item.label }}</option>
        </select>
      </div>
      <StatePanel
        :loading="list.isPending.value"
        :error="list.error.value"
        :empty="list.data.value?.items.length === 0"
        :title="q || category ? 'Không có bài phù hợp' : 'Chưa có kiến thức nào'"
        description="Viết hướng dẫn sử dụng, mô tả quy trình hoặc câu hỏi thường gặp. Có thể nhập từ tệp .md/.txt hoặc từ gói nghiệp vụ đã phát hành."
        @retry="list.refetch()"
        ><button class="button small" type="button" @click="openNew"><Plus :size="15" />Viết bài đầu tiên</button></StatePanel
      >
      <article v-for="item in list.data.value?.items" :key="item.id" class="knowledge-row" :class="{ draft: !item.published }">
        <div class="grow">
          <strong>{{ item.title }}</strong>
          <small
            ><span class="knowledge-tag" :class="item.category">{{ item.category_label }}</span>
            <span v-if="item.source === 'package'" class="knowledge-tag source"><Workflow :size="11" />Từ gói nghiệp vụ</span>
            <span v-if="!item.published" class="knowledge-tag hidden"><EyeOff :size="11" />Đang ẩn</span>
            {{ item.length.toLocaleString('vi-VN') }} ký tự · sửa {{ formatDate(item.updated_at, true) }}</small
          >
          <p>{{ item.excerpt }}</p>
        </div>
        <button class="icon-button" type="button" :aria-label="`Sửa ${item.title}`" title="Sửa" @click="openEdit(item)">
          <Pencil :size="16" />
        </button>
        <button class="icon-button" type="button" :aria-label="`Xóa ${item.title}`" title="Xóa" @click="remove(item)">
          <Trash2 :size="16" />
        </button>
      </article>
    </section>
    <aside class="stack" style="align-content: start">
      <section class="card">
        <header class="card-header"><h3>Thử tìm kiến thức</h3></header>
        <form class="card-body stack" @submit.prevent="runProbe">
          <p class="muted" style="font-size: 13px">
            Gõ một câu hỏi để xem trợ lý sẽ đọc những đoạn nào. Không gọi dịch vụ AI, không tốn chi phí.
          </p>
          <div class="search-box">
            <Search :size="16" /><input v-model="probe" placeholder="Ví dụ: xin nghỉ phép thế nào" aria-label="Câu hỏi thử" />
          </div>
          <button class="button secondary small" :disabled="probing || !probe.trim()">Thử tìm</button>
          <template v-if="probeResult">
            <p v-if="!probeResult.length" class="muted" style="font-size: 13px">
              Không tìm thấy đoạn nào. Trợ lý sẽ trả lời là chưa có hướng dẫn.
            </p>
            <div v-for="(item, index) in probeResult" :key="index" class="probe-hit">
              <strong>[{{ index + 1 }}] {{ item.title }}</strong>
              <p>{{ item.text.slice(0, 260) }}{{ item.text.length > 260 ? '…' : '' }}</p>
            </div>
          </template>
        </form>
      </section>
    </aside>
  </div>
  <ModalDialog v-if="editorOpen" :title="editing ? 'Sửa bài kiến thức' : 'Viết bài kiến thức'" wide @close="closeEditor">
    <form class="stack" @submit.prevent="saveArticle">
      <div v-if="error" class="notice error" role="alert">{{ error }}</div>
      <div class="form-grid">
        <div class="field">
          <label for="article-title">Tiêu đề</label>
          <input id="article-title" v-model="title" maxlength="250" required placeholder="Ví dụ: Cách xin nghỉ phép" />
        </div>
        <div class="field">
          <label for="article-category">Loại</label>
          <select id="article-category" v-model="kind">
            <option v-for="item in categories" :key="item.key" :value="item.key">{{ item.label }}</option>
          </select>
        </div>
      </div>
      <div class="field">
        <label for="article-body" class="article-body-label"
          ><span>Nội dung</span
          ><span class="file-pick"
            ><FileUp :size="14" />Nhập từ tệp .md / .txt<input type="file" accept=".md,.txt,text/plain,text/markdown" @change="importFile"
          /></span>
        </label>
        <textarea
          id="article-body"
          v-model="body"
          rows="16"
          maxlength="50000"
          required
          placeholder="Viết như đang hướng dẫn một đồng nghiệp mới: các bước, lưu ý, ai duyệt, mất bao lâu…"
        />
        <small class="muted">{{ body.length.toLocaleString('vi-VN') }} / 50.000 ký tự. Cách đoạn bằng một dòng trống.</small>
      </div>
      <label class="assistant-toggle">
        <span class="switch"><input v-model="published" type="checkbox" /><span /></span>
        <span><strong>Cho trợ lý dùng bài này</strong><small>Tắt để lưu nháp, trợ lý sẽ bỏ qua.</small></span>
      </label>
      <div class="form-actions">
        <button type="button" class="button secondary" :disabled="busy" @click="closeEditor">Hủy</button>
        <button class="button" :disabled="busy || !title.trim() || !body.trim()">{{ busy ? 'Đang lưu…' : 'Lưu bài' }}</button>
      </div>
    </form>
  </ModalDialog>
  <ModalDialog v-if="packagesOpen" title="Nhập kiến thức từ quy trình" @close="packagesOpen = false">
    <p class="muted" style="margin-bottom: 14px">
      Tạo bài mô tả quy trình (thông tin cần điền, tài liệu, các bước duyệt) từ phiên bản đang áp dụng của mỗi gói.
      Khi gói đổi phiên bản, bấm “Cập nhật” để làm mới bài.
    </p>
    <StatePanel
      :loading="packages.isPending.value"
      :error="packages.error.value"
      :empty="packages.data.value?.items.length === 0"
      compact
      title="Chưa có quy trình nào đang áp dụng"
      @retry="packages.refetch()"
    />
    <div v-for="item in packages.data.value?.items" :key="item.package_id" class="list-row">
      <span class="file-icon"><PackageOpen :size="18" /></span>
      <div class="grow">
        <strong>{{ item.name }}</strong>
        <small>Phiên bản {{ item.version_no }}<template v-if="item.imported_at"> · đã nhập {{ formatDate(item.imported_at, true) }}</template></small>
      </div>
      <button class="button small" :class="{ secondary: item.article_id }" type="button" :disabled="!!importing" @click="importPackage(item)">
        {{ importing === item.package_id ? 'Đang nhập…' : item.article_id ? 'Cập nhật' : 'Nhập' }}
      </button>
    </div>
  </ModalDialog>
</template>
