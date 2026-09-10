import { apiClient, toApiError } from './apiClient'
import type { DemoResetPreview, DemoResetResult, DemoSimulationInput, DemoSimulationResult } from '../types/demo'

export async function simulateDemoSale(input: DemoSimulationInput): Promise<DemoSimulationResult> {
  try {
    const response = await apiClient.post<DemoSimulationResult>('/demo/simulate', input)
    return response.data
  } catch (error) {
    throw toApiError(error)
  }
}

export async function getDemoResetPreview(): Promise<DemoResetPreview> {
  try {
    const response = await apiClient.get<DemoResetPreview>('/demo/reset-preview')
    return response.data
  } catch (error) {
    throw toApiError(error)
  }
}

export async function resetDemoData(): Promise<DemoResetResult> {
  try {
    const response = await apiClient.post<DemoResetResult>('/demo/reset')
    return response.data
  } catch (error) {
    throw toApiError(error)
  }
}
