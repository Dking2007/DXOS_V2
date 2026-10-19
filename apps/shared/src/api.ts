export interface Page<T> {
  items: T[]
  next_cursor: string | null
  has_more: boolean
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public traceId?: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

export function errorText(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 409)
      return 'Dữ liệu đã thay đổi hoặc yêu cầu bị xung đột. Tải lại bản mới trước khi tiếp tục.'
    if (error.status === 403)
      return 'Bạn không có quyền thực hiện thao tác này.'
    if (error.status === 401)
      return 'Phiên đăng nhập đã hết hạn. Đăng nhập lại để tiếp tục.'
    return error.message
  }
  return error instanceof Error
    ? error.message
    : 'Không thể kết nối hệ thống. Kiểm tra kết nối và thử lại.'
}

export function csrfCookie(scope: 'workspace' | 'core'): string {
  const key = `dx_${scope}_csrf=`
  const value = document.cookie
    .split(';')
    .map((item) => item.trim())
    .find((item) => item.startsWith(key))
  return value ? decodeURIComponent(value.slice(key.length)) : ''
}

export function createApi(scope: 'workspace' | 'core') {
  let csrf = ''
  const prefix = `/${scope}/v1`
  return {
    setCsrf(token: string) {
      csrf = token
    },
    async request<T>(path: string, options: RequestInit = {}): Promise<T> {
      const headers = new Headers(options.headers)
      if (
        options.body &&
        !(options.body instanceof FormData) &&
        !(options.body instanceof Blob)
      )
        headers.set('Content-Type', 'application/json')
      if (!['GET', 'HEAD'].includes(options.method ?? 'GET'))
        headers.set('X-CSRF-Token', csrf || csrfCookie(scope))
      let response: Response
      try {
        response = await fetch(`${prefix}${path}`, {
          ...options,
          credentials: 'include',
          headers,
        })
      } catch {
        throw new ApiError(
          0,
          'network_error',
          'Không thể kết nối máy chủ. Kiểm tra kết nối và thử lại.',
        )
      }
      if (!response.ok) {
        const body = (await response.json().catch(() => ({}))) as Record<
          string,
          unknown
        >
        const detail =
          typeof body.detail === 'string'
            ? body.detail
            : 'Yêu cầu không hợp lệ. Kiểm tra thông tin đã nhập.'
        throw new ApiError(
          response.status,
          String(body.code ?? 'request_failed'),
          detail,
          typeof body.trace_id === 'string'
            ? body.trace_id
            : (response.headers.get('X-Trace-Id') ?? undefined),
        )
      }
      if (response.status === 204) return undefined as T
      return (await response.json()) as T
    },
  }
}

export function queryString(
  values: Record<string, string | number | boolean | null | undefined>,
): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(values))
    if (value !== undefined && value !== null && value !== '')
      params.set(key, String(value))
  const text = params.toString()
  return text ? `?${text}` : ''
}

export function newIntent(): string {
  return crypto.randomUUID()
}
export function formatDate(value?: string | null, withTime = false): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat(
    'vi-VN',
    withTime
      ? {
          day: '2-digit',
          month: '2-digit',
          year: 'numeric',
          hour: '2-digit',
          minute: '2-digit',
        }
      : { day: '2-digit', month: '2-digit', year: 'numeric' },
  ).format(date)
}
export function formatSize(bytes: number): string {
  if (!bytes) return '0 B'
  const unit = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), 3)
  return `${(bytes / 1024 ** unit).toLocaleString('vi-VN', { maximumFractionDigits: 1 })} ${['B', 'KB', 'MB', 'GB'][unit]}`
}
