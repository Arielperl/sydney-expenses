import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

export const apiClient = axios.create({
  baseURL: `${API_BASE_URL}/api`,
  // The fetch adapter is what MSW (used in tests) reliably intercepts; it also
  // avoids a known XHR + FormData/File hang under jsdom.
  adapter: 'fetch',
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
          : error.message
    return new ApiError(message, error.response?.status)
  }
  return new ApiError('An unexpected error occurred.')
}
