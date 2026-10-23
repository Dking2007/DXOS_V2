// Plain-language names for permission codes and roles, shared by every screen that shows them.
export interface PermissionInfo {
  label: string
  hint: string
  group: string
}

export const PERMISSIONS: Record<string, PermissionInfo> = {
  'cases.create': { label: 'Tạo và trình hồ sơ', hint: 'Lập hồ sơ từ mẫu và gửi đi duyệt.', group: 'Hồ sơ' },
  'cases.read.department': { label: 'Xem hồ sơ của phòng', hint: 'Xem mọi hồ sơ do người trong phòng mình lập.', group: 'Hồ sơ' },
  'cases.read.organization': { label: 'Xem hồ sơ toàn cơ quan', hint: 'Xem hồ sơ của tất cả phòng ban.', group: 'Hồ sơ' },
  'forms.manage': { label: 'Thiết kế mẫu hồ sơ', hint: 'Tạo, sửa và phát hành mẫu biểu.', group: 'Hồ sơ' },
  'tasks.create': { label: 'Tạo công việc', hint: 'Tự tạo việc và giao cho người khác.', group: 'Công việc' },
  'tasks.assign.department': { label: 'Giao việc trong phòng', hint: 'Giao việc cho bất kỳ ai trong phòng mình.', group: 'Công việc' },
  'tasks.assign.organization': { label: 'Giao việc toàn cơ quan', hint: 'Giao việc cho mọi phòng ban.', group: 'Công việc' },
  'drive.use': { label: 'Dùng kho tài liệu', hint: 'Tải lên, chia sẻ và soạn tài liệu.', group: 'Tài liệu' },
  'feed.post': { label: 'Đăng bài lên bảng tin', hint: 'Viết bài và bình luận.', group: 'Trao đổi' },
  'feed.official': { label: 'Đăng thông báo chính thức', hint: 'Đánh dấu bài là thông báo của cơ quan.', group: 'Trao đổi' },
  'feed.moderate': { label: 'Kiểm duyệt bảng tin', hint: 'Ẩn hoặc gỡ bài của người khác.', group: 'Trao đổi' },
  'automations.manage': { label: 'Thiết kế tự động hóa', hint: 'Tạo và bật luồng tự động.', group: 'Quản trị' },
  'organization.manage': { label: 'Quản lý tổ chức', hint: 'Phòng ban, thành viên và vai trò.', group: 'Quản trị' },
  'audit.read': { label: 'Xem nhật ký hệ thống', hint: 'Tra cứu ai đã làm gì, khi nào.', group: 'Quản trị' },
}

export const PERMISSION_GROUPS = ['Hồ sơ', 'Công việc', 'Tài liệu', 'Trao đổi', 'Quản trị']

export function permissionLabel(code: string): string {
  return PERMISSIONS[code]?.label ?? code
}

export const ROLE_LABELS: Record<string, string> = {
  director: 'Ban giám đốc',
  manager: 'Lãnh đạo phòng',
  staff: 'Cán bộ / nhân viên',
  technical_admin: 'Quản trị kỹ thuật',
}

export function roleLabel(role?: string | null): string {
  return ROLE_LABELS[role ?? ''] ?? ROLE_LABELS.staff
}
