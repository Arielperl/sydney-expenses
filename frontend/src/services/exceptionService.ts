import { apiClient, toApiError } from './apiClient'
import type { ExceptionCenter } from '../types/exceptions'

export async function getExceptionCenter(): Promise<ExceptionCenter> {
  try {
    const response = await apiClient.get<ExceptionCenter>('/exceptions')
    return response.data
  } catch (error) {
    throw toApiError(error)
  }
}
