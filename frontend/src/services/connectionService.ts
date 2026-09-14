import { apiClient, toApiError } from './apiClient'
import type { ConnectionWithSecret, IntegrationConnection } from '../types/connections'

export async function listConnections(): Promise<IntegrationConnection[]> {
  try {
    return (await apiClient.get<IntegrationConnection[]>('/connections')).data
  } catch (error) {
    throw toApiError(error)
  }
}

export async function createConnection(name: string): Promise<ConnectionWithSecret> {
  try {
    return (await apiClient.post<ConnectionWithSecret>('/connections', { name, provider: 'demo-pay' })).data
  } catch (error) {
    throw toApiError(error)
  }
}

export async function setConnectionEnabled(id: string, enabled: boolean): Promise<IntegrationConnection> {
  try {
    return (await apiClient.patch<IntegrationConnection>(`/connections/${id}`, { enabled })).data
  } catch (error) {
    throw toApiError(error)
  }
}

export async function rotateConnectionSecret(id: string): Promise<ConnectionWithSecret> {
  try {
    return (await apiClient.post<ConnectionWithSecret>(`/connections/${id}/rotate-secret`)).data
  } catch (error) {
    throw toApiError(error)
  }
}
