import { apiClient, toApiError } from './apiClient'
import type { ExceptionCenter } from '../types/exceptions'

export async function getExceptionCenter(limit = 20): Promise<ExceptionCenter> {
  try {
    const response = await apiClient.get<ExceptionCenter>('/exceptions', { params: { limit } })
    return response.data
  } catch (error) {
    throw toApiError(error)
  }
}
