import { ref } from 'vue'

export interface TourStep {
  target?: string
  title: string
  body: string
}

const KEY = 'dx-workspace-tour-v1'
export const tourOpen = ref(false)

function seenKey(userId: string) {
  return `${KEY}:${userId}`
}
export function tourSeen(userId: string) {
  try {
    return window.localStorage.getItem(seenKey(userId)) === '1'
  } catch {
    // Without storage we cannot remember; do not show the tour on every visit.
    return true
  }
}
export function markTourSeen(userId: string) {
  try {
    window.localStorage.setItem(seenKey(userId), '1')
  } catch {
    // Ignored: the tour simply shows again next time.
  }
}
export function startTour() {
  tourOpen.value = true
}

const COMMON: TourStep[] = [
  {
    title: 'Chào mừng đến Desktiny',
    body: 'Vài bước ngắn để bạn biết mọi thứ nằm ở đâu. Bạn có thể bỏ qua và xem lại bất cứ lúc nào trong Thiết lập › Giao diện.',
  },
  {
    target: 'nav',
    title: 'Menu theo nhóm việc',
    body: 'Làm việc, Trao đổi, Tài liệu và Quản trị. Số màu đỏ cho biết có bao nhiêu việc đang chờ bạn ở từng mục.',
  },
  {
    target: 'create',
    title: 'Tạo mới từ bất cứ đâu',
    body: 'Giao việc, lập hồ sơ, soạn tài liệu, viết bài hay mở hội thoại — tất cả trong một nút.',
  },
  {
    target: 'search',
    title: 'Tìm nhanh bằng Ctrl + K',
    body: 'Gõ tên việc, hồ sơ, tài liệu hoặc một lệnh như “giao việc”. Dùng phím mũi tên và Enter để mở.',
  },
  {
    target: 'notifications',
    title: 'Thông báo gọn một chỗ',
    body: 'Lọc theo phê duyệt, công việc, lời nhắc và đánh dấu tất cả đã đọc chỉ với một lần bấm.',
  },
]

const BY_ROLE: Record<string, TourStep[]> = {
  staff: [
    {
      target: 'agenda',
      title: 'Bắt đầu ngày làm việc ở đây',
      body: 'Việc được giao, việc quá hạn và lời nhắc được xếp theo mức gấp. Bấm “Nhận việc” ngay trên danh sách.',
    },
  ],
  manager: [
    {
      target: 'agenda',
      title: 'Việc của bạn và của phòng',
      body: 'Ngoài việc của mình, bạn thấy việc phòng nhận cần phân công, kết quả cần xem và hồ sơ chờ duyệt.',
    },
  ],
  director: [
    {
      target: 'agenda',
      title: 'Những gì cần bạn quyết định',
      body: 'Hồ sơ chờ duyệt và kết quả công việc cần xem đứng đầu danh sách. Khi vắng mặt, dùng “Ủy quyền duyệt” trong mục Cần phê duyệt.',
    },
  ],
  technical_admin: [
    {
      target: 'nav-admin',
      title: 'Khu vực quản trị',
      body: 'Phòng ban, thành viên, vai trò và luồng tự động nằm trong nhóm Quản trị. Quyền quản trị kỹ thuật không cho xem nội dung hồ sơ.',
    },
  ],
}

export function stepsFor(role?: string | null): TourStep[] {
  return [...COMMON, ...(BY_ROLE[role ?? ''] ?? BY_ROLE.staff)]
}
