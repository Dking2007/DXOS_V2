// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
// The colour of a dossier's folder in the list: where it stands at a glance.
export type FolderTone = 'draft' | 'moving' | 'attention' | 'done' | 'stopped' | 'archived'

const TONES: Record<string, FolderTone> = {
  draft: 'draft',
  pending_workflow_start: 'moving',
  submitted: 'moving',
  processing: 'moving',
  needs_revision: 'attention',
  approved: 'done',
  rejected: 'stopped',
  cancelled: 'stopped',
  withdrawn: 'archived',
}

export function caseTone(status: string, archivedAt?: string | null): FolderTone {
  if (archivedAt) return 'archived'
  return TONES[status] ?? 'draft'
}
