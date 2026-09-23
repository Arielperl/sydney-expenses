import { apiClient, toApiError } from './apiClient'
import type { PaymentProvider } from './businessService'

export interface AdminBusiness {
  id: string
  name: string
  business_number: string | null
  created_at: string
  owner_emails: string[]
  payment_providers: PaymentProvider[]
  member_count: number
  sale_count: number
  connection_count: number
}

export async function listAdminBusinesses(): Promise<AdminBusiness[]> {
  try { return (await apiClient.get<AdminBusiness[]>('/admin/businesses')).data }
  catch (error) { throw toApiError(error) }
}

export async function addBusinessProvider(businessId: string, provider: PaymentProvider): Promise<void> {
  try { await apiClient.post(`/admin/businesses/${businessId}/payment-providers/${provider}`) }
  catch (error) { throw toApiError(error) }
}

export async function removeBusinessProvider(businessId: string, provider: PaymentProvider): Promise<void> {
  try { await apiClient.delete(`/admin/businesses/${businessId}/payment-providers/${provider}`) }
  catch (error) { throw toApiError(error) }
}

export async function deleteBusinessAsAdmin(businessId: string, confirmName: string): Promise<void> {
  try { await apiClient.delete(`/admin/businesses/${businessId}`, { data: { confirm_name: confirmName } }) }
  catch (error) { throw toApiError(error) }
}
