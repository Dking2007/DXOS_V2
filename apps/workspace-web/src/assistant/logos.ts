// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
// Official brand marks of the AI services, from @lobehub/icons-static-svg (MIT). Each logo is
// a trademark of its owner and is shown only to say which service is configured. Self-hosted
// gateways have no brand, so they get a plain icon for the protocol they speak. Ollama and
// vLLM are model servers the office runs itself; they keep their own marks.
import claude from '@lobehub/icons-static-svg/icons/claude-color.svg?url'
import deepseek from '@lobehub/icons-static-svg/icons/deepseek-color.svg?url'
import gemini from '@lobehub/icons-static-svg/icons/gemini-color.svg?url'
import ollama from '@lobehub/icons-static-svg/icons/ollama.svg?url'
import openai from '@lobehub/icons-static-svg/icons/openai.svg?url'
import vllm from '@lobehub/icons-static-svg/icons/vllm-color.svg?url'
import type { Component } from 'vue'
import { Braces, MessagesSquare, Server } from 'lucide-vue-next'
import type { AssistantProvider } from '@dx/web-shared/types.ts'

export const PROVIDER_LOGOS: Partial<Record<AssistantProvider['kind'], string>> = {
  anthropic: claude,
  openai,
  gemini,
  deepseek,
  ollama,
  vllm,
}

export const GATEWAY_ICONS: Partial<Record<AssistantProvider['kind'], Component>> = {
  custom_anthropic: Server,
  custom_chat: MessagesSquare,
  custom_responses: Braces,
}

/** Short protocol name shown on a gateway tile. */
export const GATEWAY_PROTOCOLS: Partial<Record<AssistantProvider['kind'], string>> = {
  custom_anthropic: 'Anthropic Messages',
  custom_chat: 'OpenAI Chat Completions',
  custom_responses: 'OpenAI Responses',
}

const PATHS: Partial<Record<AssistantProvider['kind'], string>> = {
  custom_anthropic: '/messages',
  custom_chat: '/chat/completions',
  custom_responses: '/responses',
  vllm: '/chat/completions',
  ollama: '/api/chat',
}

/** The address a gateway will be called at, normalised the way the server does it. */
export function gatewayEndpoint(kind: AssistantProvider['kind'], base: string): string {
  const path = PATHS[kind]
  let value = base.trim().replace(/\/+$/, '')
  if (!path || !/^https?:\/\/[^/\s]+/i.test(value)) return ''
  // Ollama's own API sits at the server root, without a version segment.
  if (kind === 'ollama') return value.replace(/\/(v1|api)$/, '') + path
  if (!/\/v\d+$/.test(value)) value += '/v1'
  return value + path
}
