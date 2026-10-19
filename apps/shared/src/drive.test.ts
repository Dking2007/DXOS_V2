import { describe, expect, it } from 'vitest'
import {
  copySummary,
  folderGrantsPending,
  labelsToText,
  parseLabels,
  shareLabel,
} from './drive'
import type { Share, User } from './types'

const users: User[] = [{ id: 'u1', subject: 'b', display_name: 'Nguyễn B' }]
const base: Share = {
  id: 's1',
  resource_type: 'folder',
  resource_id: 'f1',
  user_id: 'u1',
  access: 'read',
}

describe('folder share labels', () => {
  it('names a known recipient and their access level', () => {
    expect(shareLabel(base, users)).toBe('Nguyễn B · được xem và tải')
    expect(shareLabel({ ...base, access: 'write' }, users)).toBe(
      'Nguyễn B · được chỉnh sửa',
    )
    expect(shareLabel({ ...base, access: 'none' }, users)).toBe(
      'Nguyễn B · đã thu hồi',
    )
  })
  it('falls back to a short id when the recipient is unknown', () => {
    expect(shareLabel({ ...base, user_id: 'unknown-user-id' }, [])).toContain(
      'unknown-',
    )
  })
  it('treats an empty folder as having current grants', () => {
    expect(folderGrantsPending({})).toBe(false)
    expect(folderGrantsPending({ acl_state: 'syncing' })).toBe(true)
    expect(folderGrantsPending({ acl_state: 'ready' })).toBe(false)
  })
})

describe('labels', () => {
  it('deduplicates case-insensitively, trims and sorts', () => {
    expect(parseLabels(' Hợp đồng , hợp đồng ,Khẩn,  Mẫu ')).toEqual([
      'Hợp đồng',
      'Khẩn',
      'Mẫu',
    ])
  })
  it('drops empty entries rather than keeping a blank label', () => {
    expect(parseLabels('A, ,  , B,')).toEqual(['A', 'B'])
  })
  it('round-trips through the editable text form', () => {
    expect(labelsToText(parseLabels('B, A'))).toBe('A, B')
    expect(labelsToText([])).toBe('')
    expect(labelsToText(undefined)).toBe('')
  })
  it('keeps the first spelling when two differ only by case', () => {
    expect(parseLabels('Hợp Đồng, hợp đồng')).toEqual(['Hợp Đồng'])
  })
})

describe('copy summary', () => {
  it('names the document and carries its labels', () => {
    expect(copySummary({ name: 'bản gốc.docx', labels: ['Pháp chế'] })).toBe(
      'Bản sao của “bản gốc.docx” gồm nội dung phiên bản hiện tại. Nhãn "Pháp chế" được giữ nguyên.',
    )
  })
  it('says nothing about labels when there are none', () => {
    expect(copySummary({ name: 'trống.docx' })).not.toContain('Nhãn')
  })
})
