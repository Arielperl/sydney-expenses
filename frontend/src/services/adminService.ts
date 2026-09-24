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

export interface StaffUser { id: string; email: string; name: string; system_role: 'user' | 'support' | 'admin'; business_name: string | null }

export async function listStaffUsers(): Promise<StaffUser[]> {
  try { return (await apiClient.get<StaffUser[]>('/support/staff/users')).data }
  catch (error) { throw toApiError(error) }
}

export async function deleteStaffUser(id: string): Promise<void> {
  try { await apiClient.delete(`/support/staff/users/${id}`) }
  catch (error) { throw toApiError(error) }
}

export async function listAdminBusinesses(): Promise<AdminBusiness[]> {
  try { return (await apiClient.get<AdminBusiness[]>('/support/staff/businesses')).data }
  catch (error) { throw toApiError(error) }
}

export async function addBusinessProvider(businessId: string, provider: PaymentProvider): Promise<void> {
  try { await apiClient.post(`/support/staff/businesses/${businessId}/payment-providers/${provider}`) }
  catch (error) { throw toApiError(error) }
}

export async function removeBusinessProvider(businessId: string, provider: PaymentProvider): Promise<void> {
  try { await apiClient.delete(`/support/staff/businesses/${businessId}/payment-providers/${provider}`) }
  catch (error) { throw toApiError(error) }
}
