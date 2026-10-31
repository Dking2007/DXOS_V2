// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
// Plain-language text for audit log entries: what was done, and where the record lives.
const SUBJECTS: Record<string, { label: string; route?: string }> = {
  case: { label: 'Hồ sơ', route: '/cases/' },
  task: { label: 'Công việc', route: '/tasks/' },
  automation: { label: 'Tự động hóa', route: '/automations/' },
  package: { label: 'Gói nghiệp vụ' },
  form: { label: 'Biểu mẫu' },
  file: { label: 'Tài liệu' },
  folder: { label: 'Thư mục' },
  user: { label: 'Thành viên' },
  department: { label: 'Phòng ban' },
  role: { label: 'Vai trò' },
  post: { label: 'Bảng tin' },
  conversation: { label: 'Cuộc trò chuyện' },
  delegation: { label: 'Ủy quyền' },
  connection: { label: 'Kết nối' },
  assistant: { label: 'Trợ lý AI' },
  field_evidence: { label: 'Căn cứ trường' },
  office: { label: 'Soạn thảo trực tuyến' },
}

const VERBS: Record<string, string> = {
  created: 'tạo mới',
  updated: 'cập nhật',
  deleted: 'xóa',
  submitted: 'trình duyệt',
  withdrawn: 'rút lại',
  published: 'phát hành',
  validated: 'kiểm chứng',
  simulated: 'chạy thử',
  version_created: 'tạo phiên bản',
  imported_template: 'tạo từ mẫu',
  attachment_download: 'tải tệp đính kèm',
  source_download: 'tải tài liệu gốc',
  uploaded: 'tải lên',
  share_changed: 'đổi chia sẻ',
  version_restored: 'khôi phục phiên bản',
  assigned: 'giao việc',
  enabled: 'bật',
  disabled: 'tắt',
  attached: 'gắn vào việc',
  detached: 'gỡ khỏi việc',
  run_manual: 'chạy thủ công',
  pinned: 'ghim',
  unpinned: 'bỏ ghim',
  revoked: 'thu hồi',
  member_removed: 'xóa thành viên',
  config_updated: 'đổi cấu hình',
  provider_activated: 'chọn dịch vụ AI',
  provider_updated: 'cập nhật dịch vụ AI',
  provider_deleted: 'xóa dịch vụ AI',
  article_created: 'thêm bài kiến thức',
  article_updated: 'sửa bài kiến thức',
  article_deleted: 'xóa bài kiến thức',
  article_imported: 'nhập bài kiến thức',
  provider_created: 'thêm dịch vụ AI',
  reviewed: 'đối chiếu',
  members_added: 'thêm thành viên',
  opened: 'mở tài liệu',
  copied: 'sao chép',
  decision: 'quyết định duyệt',
  accept: 'tiếp nhận',
  start: 'bắt đầu làm',
  submit: 'nộp kết quả',
  complete: 'nghiệm thu',
  return: 'trả lại',
  block: 'báo vướng mắc',
  unblock: 'gỡ vướng mắc',
  cancel: 'hủy',
  cancelled: 'hủy hồ sơ',
  archived: 'lưu trữ',
  unarchived: 'bỏ lưu trữ',
}

/** Whether both parts of an action code have Vietnamese text (used by the tests). */
export function auditKnown(action: string): boolean {
  const [subject, ...rest] = action.split('.')
  return subject in SUBJECTS && rest.join('.') in VERBS
}

export function auditSubject(action: string) {
  return SUBJECTS[action.split('.')[0]] ?? { label: action.split('.')[0] }
}

export function auditLabel(action: string): string {
  const [subject, ...rest] = action.split('.')
  const verb = rest.join('.')
  const name = SUBJECTS[subject]?.label ?? subject
  return `${name}: ${VERBS[verb] ?? verb.replaceAll('_', ' ')}`
}

/** Link to the record an entry concerns, when the app has a page for it. */
export function auditLink(action: string, resourceId: string): string | null {
  const route = auditSubject(action).route
  return route && resourceId ? route + resourceId : null
}
