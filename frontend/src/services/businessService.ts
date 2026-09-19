import { apiClient, toApiError } from './apiClient'
import type { ConnectionProvider } from '../types/connections'

export type PaymentProvider = Extract<ConnectionProvider, 'grow' | 'cardcom'>

export async function getBusinessPaymentProviders(): Promise<PaymentProvider[]> {
  try {
    const response = await apiClient.get<{ providers: PaymentProvider[] }>('/businesses/current/payment-providers')
    return response.data.providers
  } catch (error) {
    throw toApiError(error)
  }
}
