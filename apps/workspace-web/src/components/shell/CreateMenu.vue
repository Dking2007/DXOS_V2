<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  FilePlus2,
  FileText,
  ListPlus,
  MessageSquarePlus,
  Plus,
  SquarePen,
  Upload,
} from 'lucide-vue-next'
import { useSession } from '../../stores/session'
import { useDismiss } from '../../ui/popover'

const session = useSession()
const route = useRoute()
const router = useRouter()
const open = ref(false)
const root = ref<HTMLElement>()
const trigger = ref<HTMLButtonElement>()
useDismiss(root, open, trigger)

const ALL = [
  { label: 'Giao việc', hint: 'Giao cho người hoặc phòng, đặt hạn', icon: ListPlus, path: '/tasks', query: { create: '1' }, capability: 'tasks.create' },
  { label: 'Hồ sơ trình duyệt', hint: 'Chọn mẫu, điền thông tin, gửi duyệt', icon: FilePlus2, path: '/cases', query: { create: '1' }, capability: 'cases.create' },
  { label: 'Tài liệu soạn thảo', hint: 'Văn bản, bảng tính hoặc trình chiếu', icon: FileText, path: '/drive', query: { create: 'document' }, capability: 'drive.use' },
  { label: 'Tải tệp lên', hint: 'Đưa tệp từ máy vào kho', icon: Upload, path: '/drive', query: { create: 'upload' }, capability: 'drive.use' },
  { label: 'Bài đăng bảng tin', hint: 'Chia sẻ với phòng hoặc cơ quan', icon: SquarePen, path: '/feed', query: { compose: '1' }, capability: 'feed.post' },
  { label: 'Hội thoại mới', hint: 'Nhắn riêng hoặc lập nhóm', icon: MessageSquarePlus, path: '/chat', query: { new: '1' } },
]
const items = computed(() => ALL.filter((item) => !item.capability || session.can(item.capability)))

async function go(item: (typeof ALL)[number]) {
  open.value = false
  // Already on that screen with the same request: clear it first so the view reacts again.
  if (route.path === item.path && Object.keys(item.query).some((key) => route.query[key]))
    await router.replace(item.path)
  await router.push({ path: item.path, query: item.query })
}
</script>
<template>
  <div ref="root" class="create-menu">
    <button
      ref="trigger"
      class="button create-trigger"
      type="button"
      aria-haspopup="menu"
      :aria-expanded="open"
      @click="open = !open"
    >
      <Plus :size="17" /><span>Tạo mới</span>
    </button>
    <div v-if="open" class="dropdown create-dropdown" role="menu" aria-label="Tạo mới">
      <button v-for="item in items" :key="item.label" type="button" role="menuitem" @click="go(item)">
        <span class="dropdown-icon"><component :is="item.icon" :size="18" /></span>
        <span><strong>{{ item.label }}</strong><small>{{ item.hint }}</small></span>
      </button>
    </div>
  </div>
</template>
