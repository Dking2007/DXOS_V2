import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  ApiError,
  createApi,
  errorText,
  formatDate,
  formatSize,
  queryString,
} from './api'
afterEach(() => vi.unstubAllGlobals())
describe('API error and formatting contract', () => {
  it('preserves conflicts and trace identifiers', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            code: 'revision_conflict',
            detail: 'Stale',
            trace_id: 'trace-123',
          }),
          { status: 409 },
        ),
      ),
    )
    const api = createApi('workspace')
    api.setCsrf('csrf-test')
    await expect(
      api.request('/cases/1', { method: 'PATCH', body: '{}' }),
    ).rejects.toMatchObject({
      status: 409,
      code: 'revision_conflict',
      traceId: 'trace-123',
    })
  })
  it('sends server session credentials and CSRF header, never bearer storage', async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ id: 'x' })))
    vi.stubGlobal('fetch', fetcher)
    const api = createApi('workspace')
    api.setCsrf('csrf-test')
    await api.request('/cases', { method: 'POST', body: '{}' })
    const [, options] = fetcher.mock.calls[0]!
    expect(options.credentials).toBe('include')
    expect(options.headers.get('X-CSRF-Token')).toBe('csrf-test')
    expect(options.headers.get('Authorization')).toBeNull()
  })
  it('shows actionable revision conflicts', () => {
    expect(errorText(new ApiError(409, 'conflict', 'detail'))).toContain(
      'Tải lại bản mới',
    )
    expect(errorText(new ApiError(401, 'auth', 'detail'))).toContain(
      'Đăng nhập lại',
    )
  })
  it('does not serialize empty cursor or folder ID', () => {
    expect(
      queryString({ folder_id: null, q: '', trash: false, limit: 10 }),
    ).toBe('?trash=false&limit=10')
  })
  it('handles missing dates and finite file units', () => {
    expect(formatDate(null)).toBe('—')
    expect(formatSize(0)).toBe('0 B')
    expect(formatSize(1024)).toBe('1 KB')
  })
})
