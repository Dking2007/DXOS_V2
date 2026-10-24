// Which files the in-app viewer can show, decided by name (and type when the server sent one).
export type PreviewKind = 'image' | 'pdf' | 'video' | 'audio' | 'text'

const BY_EXTENSION: Record<string, PreviewKind> = {
  png: 'image',
  jpg: 'image',
  jpeg: 'image',
  gif: 'image',
  webp: 'image',
  pdf: 'pdf',
  mp4: 'video',
  m4v: 'video',
  mov: 'video',
  webm: 'video',
  mp3: 'audio',
  ogg: 'audio',
  wav: 'audio',
  txt: 'text',
  csv: 'text',
}

export function previewKind(name: string, mime?: string | null): PreviewKind | null {
  const extension = name.split('.').pop()?.toLowerCase() ?? ''
  if (BY_EXTENSION[extension]) return BY_EXTENSION[extension]
  if (!mime) return null
  if (mime === 'application/pdf') return 'pdf'
  // SVG is deliberately not an image here: it can carry script.
  if (/^image\/(png|jpeg|gif|webp)$/.test(mime)) return 'image'
  if (mime.startsWith('video/')) return 'video'
  if (mime.startsWith('audio/')) return 'audio'
  if (mime === 'text/plain' || mime === 'text/csv') return 'text'
  return null
}

/** Text files larger than this are cut, so a huge CSV cannot freeze the page. */
export const TEXT_PREVIEW_LIMIT = 512 * 1024

export function isOfficeFile(name: string) {
  return /\.(docx|xlsx|pptx|doc|xls|ppt|odt|ods|odp)$/i.test(name)
}
