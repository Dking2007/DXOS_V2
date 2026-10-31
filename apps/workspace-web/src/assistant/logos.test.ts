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
  it('shows nothing for official services or half-typed addresses', () => {
    expect(gatewayEndpoint('anthropic', 'https://gw.example.com')).toBe('')
    expect(gatewayEndpoint('custom_chat', 'gw.example')).toBe('')
  })
})
