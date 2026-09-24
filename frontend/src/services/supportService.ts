import { apiClient, toApiError } from './apiClient'

export interface SupportRequest {
  id: string
  business_id: string
  business_name: string | null
  requester_email: string | null
  subject: string
  message: string
  provider: string | null
  status: 'open' | 'resolved'
  created_at: string
}

export async function createSupportRequest(payload: { subject: string; message: string; provider?: string }): Promise<SupportRequest> {
  try { return (await apiClient.post<SupportRequest>('/support/requests', payload)).data }
  catch (error) { throw toApiError(error) }
}

export async function listOwnSupportRequests(): Promise<SupportRequest[]> {
  try { return (await apiClient.get<SupportRequest[]>('/support/requests')).data }
  catch (error) { throw toApiError(error) }
}

export async function listStaffSupportRequests(): Promise<SupportRequest[]> {
  try { return (await apiClient.get<SupportRequest[]>('/support/staff/requests')).data }
  catch (error) { throw toApiError(error) }
}

export async function setSupportRequestStatus(id: string, status: 'open' | 'resolved'): Promise<void> {
  try { await apiClient.patch(`/support/staff/requests/${id}`, { status }) }
  catch (error) { throw toApiError(error) }
}
