import { apiClient, toApiError } from './apiClient'
import type { Connection, ConnectionProvider, ConnectionWithSecret, WebhookEventListResponse } from '../types/connections'

export async function listConnections(): Promise<Connection[]> {
  try {
    const response = await apiClient.get<Connection[]>('/connections')
    return response.data
  } catch (error) {
    throw toApiError(error)
  }
}

export interface CardcomCredentialsInput {
  terminalNumber: string
  apiName: string
  apiPassword?: string
}

export async function createConnection(
  name: string,
  provider: ConnectionProvider,
  cardcomCredentials?: CardcomCredentialsInput,
): Promise<ConnectionWithSecret> {
  try {
    const response = await apiClient.post<ConnectionWithSecret>('/connections', {
      name,
      provider,
      ...(cardcomCredentials
        ? {
            cardcom_terminal_number: cardcomCredentials.terminalNumber,
            cardcom_api_name: cardcomCredentials.apiName,
            cardcom_api_password: cardcomCredentials.apiPassword || undefined,
          }
        : {}),
    })
    return response.data
  } catch (error) {
    throw toApiError(error)
  }
}

export async function setConnectionEnabled(id: string, enabled: boolean): Promise<Connection> {
  try {
    const response = await apiClient.patch<Connection>(`/connections/${id}`, { enabled })
    return response.data
  } catch (error) {
    throw toApiError(error)
  }
}

export async function deleteConnection(id: string): Promise<void> {
  try {
    await apiClient.delete(`/connections/${id}`)
  } catch (error) {
    throw toApiError(error)
  }
}

export async function rotateConnectionUrl(id: string): Promise<Connection> {
  try {
    const response = await apiClient.post<Connection>(`/connections/${id}/rotate-url`)
    return response.data
  } catch (error) {
    throw toApiError(error)
  }
}

export async function listConnectionEvents(id: string): Promise<WebhookEventListResponse> {
  try {
    const response = await apiClient.get<WebhookEventListResponse>(`/connections/${id}/events`)
    return response.data
  } catch (error) {
    throw toApiError(error)
  }
}

export async function reprocessConnectionEvent(connectionId: string, eventId: string) {
  try {
    const response = await apiClient.post(`/connections/${connectionId}/events/${eventId}/reprocess`)
    return response.data
  } catch (error) {
    throw toApiError(error)
  }
}
