import { apiClient, toApiError } from './apiClient'
import type { DashboardStats } from '../types/dashboard'

export async function getDashboardStats(): Promise<DashboardStats> {
  try {
    const response = await apiClient.get<DashboardStats>('/dashboard/stats')
    return response.data
  } catch (error) {
    throw toApiError(error)
  }
}
