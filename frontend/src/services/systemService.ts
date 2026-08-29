import { apiClient, toApiError } from './apiClient'
import type { SystemCapabilities } from '../types/system'

export async function getSystemCapabilities(): Promise<SystemCapabilities> {
  try {
    const response = await apiClient.get<SystemCapabilities>('/system/capabilities')
    return response.data
  } catch (error) {
    throw toApiError(error)
  }
}
