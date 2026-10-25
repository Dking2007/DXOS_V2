// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
import { describe, expect, it } from 'vitest'
import { isOfficeFile, previewKind } from './preview'

describe('previewKind', () => {
  it('recognises viewable files by extension, ignoring case', () => {
    expect(previewKind('Bao-gia.PDF')).toBe('pdf')
    expect(previewKind('anh.jpeg')).toBe('image')
    expect(previewKind('thu-loa.mp4')).toBe('video')
    expect(previewKind('ghi-am.wav')).toBe('audio')
    expect(previewKind('danh-sach.csv')).toBe('text')
  })

  it('falls back to the content type when the name has no known extension', () => {
    expect(previewKind('scan', 'application/pdf')).toBe('pdf')
    expect(previewKind('photo', 'image/webp')).toBe('image')
    expect(previewKind('clip', 'video/quicktime')).toBe('video')
  })

  it('never previews office files, archives or SVG', () => {
    expect(previewKind('to-trinh.docx')).toBeNull()
    expect(previewKind('ho-so.zip')).toBeNull()
    expect(previewKind('logo.svg', 'image/svg+xml')).toBeNull()
    expect(previewKind('trang.html', 'text/html')).toBeNull()
    expect(isOfficeFile('bang-tinh.XLSX')).toBe(true)
    expect(isOfficeFile('bao-gia.pdf')).toBe(false)
  })
})
