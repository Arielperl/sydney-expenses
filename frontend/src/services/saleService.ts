import { apiClient, toApiError } from './apiClient'
import type { Sale, SaleFilters, SaleInput } from '../types/sale'

export async function listSales(filters: SaleFilters = {}): Promise<Sale[]> {
  try {
    const params: Record<string, string> = {}
    if (filters.search) params.search = filters.search
    if (filters.status) params.status = filters.status
    if (filters.date_from) params.date_from = filters.date_from
    if (filters.date_to) params.date_to = filters.date_to

    const response = await apiClient.get<Sale[]>('/sales', { params })
    return response.data
  } catch (error) {
    throw toApiError(error)
  }
}

export async function getSale(id: string): Promise<Sale> {
  try {
    const response = await apiClient.get<Sale>(`/sales/${id}`)
    return response.data
  } catch (error) {
    throw toApiError(error)
  }
}

export async function createSale(input: SaleInput): Promise<Sale> {
  try {
    const response = await apiClient.post<Sale>('/sales', input)
    return response.data
  } catch (error) {
    throw toApiError(error)
  }
}

export async function updateSale(id: string, input: Partial<SaleInput>): Promise<Sale> {
  try {
    const response = await apiClient.put<Sale>(`/sales/${id}`, input)
    return response.data
  } catch (error) {
    throw toApiError(error)
  }
}

export async function deleteSale(id: string): Promise<void> {
  try {
    await apiClient.delete(`/sales/${id}`)
  } catch (error) {
    throw toApiError(error)
  }
}

export async function refundSale(id: string, amount?: number): Promise<Sale> {
  try {
    const response = await apiClient.post<Sale>(`/sales/${id}/refund`, amount != null ? { amount } : {})
    return response.data
  } catch (error) {
    throw toApiError(error)
  }
}
