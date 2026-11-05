// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
// Files attached to work items live in the drive: an upload from a dialog lands in the person's
// own drive first, then its id is attached, so the file has one home and one version history.
import { newIntent } from '@dx/web-shared/api.ts'
import { api } from '../api'

export interface AttachedFile {
  id: string
  name: string | null
  size?: number
  mime?: string
  owner_id?: string
  owner_name?: string
  restricted?: boolean
}

export async function uploadToDrive(file: File): Promise<AttachedFile> {
  const form = new FormData()
  form.append('file', file)
  return api.request<AttachedFile>('/drive/files', {
    method: 'POST',
    headers: { 'Idempotency-Key': newIntent() },
    body: form,
  })
}

/** Ids in order, without repeats, so attaching the same file twice changes nothing. */
export function mergeIds(current: string[], added: string[]): string[] {
  return [...new Set([...current, ...added])]
}
