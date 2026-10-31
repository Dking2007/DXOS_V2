// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
import { describe, expect, it } from 'vitest'
import { gatewayEndpoint } from './logos'

describe('gatewayEndpoint', () => {
  it('adds the API version and the protocol path like the server does', () => {
    expect(gatewayEndpoint('custom_anthropic', 'https://gw.example.com/')).toBe('https://gw.example.com/v1/messages')
    expect(gatewayEndpoint('custom_chat', 'https://gw.example.com/v1')).toBe('https://gw.example.com/v1/chat/completions')
    expect(gatewayEndpoint('custom_responses', 'https://gw.example.com/api/v2')).toBe('https://gw.example.com/api/v2/responses')
  })
  it('calls Ollama at its own API root and vLLM like a chat gateway', () => {
    expect(gatewayEndpoint('ollama', 'http://ai.lan:11434/v1')).toBe('http://ai.lan:11434/api/chat')
    expect(gatewayEndpoint('ollama', 'http://ai.lan:11434/')).toBe('http://ai.lan:11434/api/chat')
    expect(gatewayEndpoint('vllm', 'http://gpu.lan:8000')).toBe('http://gpu.lan:8000/v1/chat/completions')
  })
  it('shows nothing for official services or half-typed addresses', () => {
    expect(gatewayEndpoint('anthropic', 'https://gw.example.com')).toBe('')
    expect(gatewayEndpoint('custom_chat', 'gw.example')).toBe('')
  })
})
