// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
// One icon per task history action, shared by the activity card and its workflow canvas.
import {
  Ban,
  CalendarClock,
  Check,
  CheckCheck,
  CircleAlert,
  FilePlus2,
  Paperclip,
  PenLine,
  Play,
  RotateCcw,
  Send,
  UserRoundPlus,
  Workflow,
} from 'lucide-vue-next'
import type { Component } from 'vue'

const ICONS: Record<string, Component> = {
  created: FilePlus2,
  assigned: UserRoundPlus,
  accept: Check,
  start: Play,
  submit: Send,
  complete: CheckCheck,
  return: RotateCcw,
  block: CircleAlert,
  unblock: Play,
  cancel: Ban,
  due_changed: CalendarClock,
  automation_attached: Workflow,
  automation_detached: Workflow,
  files_changed: Paperclip,
  updated: PenLine,
}

export function activityIcon(action: string): Component {
  return ICONS[action] ?? PenLine
}
