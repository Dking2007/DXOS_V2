<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch, type Component } from 'vue'
import { useRouter } from 'vue-router'
import { useQuery } from '@tanstack/vue-query'
import {
  CornerDownLeft,
  FilePlus2,
  Files,
  FileText,
  ListChecks,
  ListPlus,
  MessageSquare,
  MessageSquarePlus,
  Moon,
  Newspaper,
  Search,
  SquarePen,
} from 'lucide-vue-next'
import { api } from '../../api'
import { useSession } from '../../stores/session'
import { visibleGroups } from '../../ui/nav'
import { cycleTheme } from '../../ui/theme'

interface Hit {
  type: string
  id: string
  title: string
  snippet: string
  link: string
}
interface Command {
  key: string
  label: string
  hint: string
  icon: Component
  section: string
  run: () => void
}

const router = useRouter()
const session = useSession()
const open = ref(false)
const text = ref('')
const debounced = ref('')
const active = ref(0)
const input = ref<HTMLInputElement>()
const dialog = ref<HTMLDialogElement>()
let timer = 0
let previous: Element | null = null

watch(text, (value) => {
  active.value = 0
  window.clearTimeout(timer)
  timer = window.setTimeout(() => (debounced.value = value.trim()), 220)
})

const search = useQuery({
  queryKey: computed(() => ['palette-search', debounced.value]),
  queryFn: () =>
    api.request<{ groups: Record<string, { items: Hit[] }> }>(
      `/search?q=${encodeURIComponent(debounced.value)}&limit=5`,
    ),
  enabled: computed(() => open.value && debounced.value.length >= 2),
})

const HIT_ICONS: Record<string, Component> = {
  task: ListChecks,
  case: Files,
  file: FileText,
  post: Newspaper,
  message: MessageSquare,
}
const HIT_LABELS: Record<string, string> = {
  task: 'Công việc',
  case: 'Hồ sơ',
  file: 'Tài liệu',
  post: 'Bảng tin',
  message: 'Tin nhắn',
}

const staticCommands = computed<Command[]>(() => {
  const go = (to: string) => () => router.push(to)
  const commands: Command[] = []
  const create: [string, string, Component, string, string?][] = [
    ['Giao việc mới', '/tasks?create=1', ListPlus, 'Tạo mới', 'tasks.create'],
    ['Tạo hồ sơ trình duyệt', '/cases?create=1', FilePlus2, 'Tạo mới', 'cases.create'],
    ['Soạn tài liệu mới', '/drive?create=document', FileText, 'Tạo mới', 'drive.use'],
    ['Viết bài lên bảng tin', '/feed?compose=1', SquarePen, 'Tạo mới', 'feed.post'],
    ['Bắt đầu hội thoại', '/chat?new=1', MessageSquarePlus, 'Tạo mới'],
  ]
  for (const [label, to, icon, section, capability] of create)
    if (!capability || session.can(capability))
      commands.push({ key: to, label, hint: '', icon, section, run: go(to) })
  for (const group of visibleGroups(session.can))
    for (const link of group.links)
      commands.push({
        key: link.to,
        label: `Mở ${link.label}`,
        hint: link.hint,
        icon: link.icon,
        section: 'Đi tới',
        run: go(link.to),
      })
  commands.push({
    key: 'theme',
    label: 'Đổi giao diện sáng / tối',
    hint: '',
    icon: Moon,
    section: 'Tùy chỉnh',
    run: cycleTheme,
  })
  return commands
})

function normalize(value: string) {
  return value.normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/đ/g, 'd').toLowerCase()
}

const results = computed<Command[]>(() => {
  const q = normalize(text.value.trim())
  const matches = staticCommands.value.filter(
    (item) => !q || normalize(`${item.label} ${item.hint}`).includes(q),
  )
  const hits: Command[] = []
  if (debounced.value.length >= 2)
    for (const [type, group] of Object.entries(search.data.value?.groups ?? {}))
      for (const hit of group.items)
        hits.push({
          key: `${type}:${hit.id}`,
          label: hit.title,
          hint: hit.snippet,
          icon: HIT_ICONS[type] ?? Search,
          section: HIT_LABELS[type] ?? 'Kết quả',
          run: () => router.push(hit.link),
        })
  const all = [...matches.slice(0, q ? 8 : 12), ...hits]
  if (q.length >= 2)
    all.push({
      key: 'full-search',
      label: `Tìm “${text.value.trim()}” trong toàn bộ`,
      hint: '',
      icon: Search,
      section: 'Tìm kiếm',
      run: () => router.push({ path: '/search', query: { q: text.value.trim() } }),
    })
  return all
})

const sections = computed(() => {
  const out: { name: string; items: { item: Command; index: number }[] }[] = []
  results.value.forEach((item, index) => {
    let section = out.find((entry) => entry.name === item.section)
    if (!section) out.push((section = { name: item.section, items: [] }))
    section.items.push({ item, index })
  })
  return out
})

async function show() {
  if (open.value) return
  previous = document.activeElement
  text.value = ''
  debounced.value = ''
  active.value = 0
  open.value = true
  await nextTick()
  dialog.value?.showModal()
  input.value?.focus()
}
function close() {
  open.value = false
  if (previous instanceof HTMLElement) previous.focus()
}
function run(item: Command | undefined) {
  if (!item) return
  close()
  item.run()
}
function onInputKey(event: KeyboardEvent) {
  const count = results.value.length
  if (event.key === 'ArrowDown') {
    event.preventDefault()
    active.value = (active.value + 1) % Math.max(count, 1)
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    active.value = (active.value - 1 + count) % Math.max(count, 1)
  } else if (event.key === 'Enter') {
    event.preventDefault()
    run(results.value[active.value])
  }
}
watch(active, async (value) => {
  await nextTick()
  document.getElementById(`palette-option-${value}`)?.scrollIntoView({ block: 'nearest' })
})
function onGlobalKey(event: KeyboardEvent) {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
    event.preventDefault()
    if (open.value) close()
    else show()
  }
}
onMounted(() => document.addEventListener('keydown', onGlobalKey))
onBeforeUnmount(() => document.removeEventListener('keydown', onGlobalKey))
defineExpose({ show })
</script>
<template>
  <dialog
    v-if="open"
    ref="dialog"
    class="palette"
    aria-label="Bảng lệnh nhanh"
    @cancel.prevent="close"
    @click="
      (event) => {
        if (event.target === dialog) close()
      }
    "
  >
    <div class="palette-input">
      <Search :size="18" />
      <input
        ref="input"
        v-model="text"
        type="text"
        role="combobox"
        aria-expanded="true"
        aria-controls="palette-list"
        :aria-activedescendant="results.length ? `palette-option-${active}` : undefined"
        aria-label="Gõ lệnh hoặc từ khóa"
        placeholder="Gõ để tìm việc, hồ sơ, tài liệu hoặc lệnh…"
        @keydown="onInputKey"
      />
      <kbd>Esc</kbd>
    </div>
    <div id="palette-list" class="palette-list" role="listbox" aria-label="Kết quả">
      <p v-if="!results.length" class="palette-empty">
        {{ search.isFetching.value ? 'Đang tìm…' : 'Không có kết quả phù hợp.' }}
      </p>
      <template v-for="section in sections" :key="section.name">
        <div class="palette-section">{{ section.name }}</div>
        <button
          v-for="{ item, index } in section.items"
          :id="`palette-option-${index}`"
          :key="item.key"
          type="button"
          role="option"
          class="palette-option"
          :class="{ active: index === active }"
          :aria-selected="index === active"
          tabindex="-1"
          @mousemove="active = index"
          @click="run(item)"
        >
          <component :is="item.icon" :size="17" />
          <span class="palette-text"
            ><strong>{{ item.label }}</strong><small v-if="item.hint">{{ item.hint }}</small></span
          >
          <CornerDownLeft v-if="index === active" :size="15" class="palette-enter" />
        </button>
      </template>
      <p v-if="search.isFetching.value && results.length" class="palette-empty">Đang tìm thêm…</p>
    </div>
    <footer class="palette-foot">
      <span><kbd>↑</kbd><kbd>↓</kbd> chọn</span><span><kbd>Enter</kbd> mở</span
      ><span><kbd>Ctrl</kbd>+<kbd>K</kbd> bật/tắt</span>
    </footer>
  </dialog>
</template>
