import { apiClient, toApiError } from './apiClient'
import type { DashboardPeriodName, DashboardStats } from '../types/dashboard'

export interface DashboardStatsParams {
  period: DashboardPeriodName
  customStart?: string
  customEnd?: string
}

export async function getDashboardStats(params: DashboardStatsParams): Promise<DashboardStats> {
  try {
    const query: Record<string, string> = { period: params.period }
    if (params.period === 'custom') {
      if (params.customStart) query.custom_start = params.customStart
      if (params.customEnd) query.custom_end = params.customEnd
    }
    const response = await apiClient.get<DashboardStats>('/dashboard/stats', { params: query })
    return response.data
  } catch (error) {
    throw toApiError(error)
  }
}
