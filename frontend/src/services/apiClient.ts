import axios from 'axios'

// Production requests must use the current site's /api rewrite so session
// cookies belong to whichever custom domain the user opened.
export const API_BASE_URL = import.meta.env.PROD
  ? ''
  : (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000')

export const apiClient = axios.create({
  baseURL: `${API_BASE_URL}/api`,
  // The fetch adapter is what MSW (used in tests) reliably intercepts; it also
  // avoids a known XHR + FormData/File hang under jsdom.
  adapter: 'fetch',
  withCredentials: true,
})

export const UPLOADS_BASE_URL = API_BASE_URL

export class ApiError extends Error {
  status?: number

  constructor(message: string, status?: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export function toApiError(error: unknown): ApiError {
  // Service functions already convert errors via this function before throwing;
  // re-converting an already-converted ApiError must be a no-op, not a downgrade
  // to a generic message (that previously discarded the real status/detail
  // whenever a page called toApiError on a mutation's already-converted error).
  if (error instanceof ApiError) {
    return error
  }
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail
    const message =
      typeof detail === 'string'
        ? detail
        : Array.isArray(detail)
          ? detail.map((item) => item.msg ?? String(item)).join('; ')
          : typeof detail?.message === 'string'
            ? detail.message
            : error.message
    return new ApiError(message, error.response?.status)
  }
  return new ApiError('An unexpected error occurred.')
}

// One refresh for concurrent failed requests; do not replay writes without a 401.
let refreshInFlight: Promise<unknown> | null = null
apiClient.interceptors.response.use(response => response, async error => {
  // The server locked the product (trial ended, subscription lapsed): let the app show why.
  if (error.response?.status === 402 && error.response?.data?.code === 'subscription_required') {
    window.dispatchEvent(new Event('sydney:subscription-required'))
  }
  const config = error.config
  if (error.response?.status !== 401 || !config || config._retried || (config.url?.startsWith('/auth/') && config.url !== '/auth/session')) return Promise.reject(error)
  config._retried = true
  try {
    refreshInFlight ??= apiClient.post('/auth/refresh').finally(() => { refreshInFlight = null })
    await refreshInFlight
    return apiClient(config)
  } catch (refreshError) {
    window.dispatchEvent(new Event('sydney:session-expired'))
    return Promise.reject(refreshError)
  }
})
