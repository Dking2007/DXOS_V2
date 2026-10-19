import type { Share, User } from './types'

/** Vietnamese label for a share row, e.g. "Nguyễn A · được xem và tải". */
export function shareAccessLabel(access: string): string {
  if (access === 'write') return 'được chỉnh sửa'
  if (access === 'none') return 'đã thu hồi'
  return 'được xem và tải'
}

export function shareRecipientName(share: Share, users: User[]): string {
  const match = users.find((user) => user.id === share.user_id)
  return match?.display_name || `${share.user_id.slice(0, 8)}…`
}

export function shareLabel(share: Share, users: User[]): string {
  return `${shareRecipientName(share, users)} · ${shareAccessLabel(share.access)}`
}

/** True while Core grants for a folder's subtree are still being recomputed. */
export function folderGrantsPending(folder: { acl_state?: string }): boolean {
  return folder.acl_state === 'syncing'
}

const LABEL_SEPARATOR = ','

/**
 * Labels as they are stored: unique, trimmed, sorted, compared without regard to case.
 * The backend applies the same rule, so the list stays stable across an edit and a save.
 */
export function parseLabels(text: string): string[] {
  const seen = new Map<string, string>()
  for (const raw of text.split(LABEL_SEPARATOR)) {
    const value = raw.trim()
    // The first spelling of a label wins, so typing it again in another case does not
    // silently change how it reads in every list.
    const key = value.toLowerCase()
    if (value && !seen.has(key)) seen.set(key, value)
  }
  return [...seen.values()].sort((a, b) => a.localeCompare(b, 'vi'))
}

/** Labels as the editable field shows them: one comma-separated line. */
export function labelsToText(labels?: string[] | null): string {
  return (labels ?? []).join(`${LABEL_SEPARATOR} `)
}

/** A sentence describing what copying a document will produce. */
export function copySummary(file: { name: string; labels?: string[] }): string {
  const carried = file.labels?.length
    ? ` Nhãn "${labelsToText(file.labels)}" được giữ nguyên.`
    : ''
  return `Bản sao của “${file.name}” gồm nội dung phiên bản hiện tại.${carried}`
}
