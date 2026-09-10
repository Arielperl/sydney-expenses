import { apiClient, toApiError } from './apiClient'
import type { ReceiptConfirmInput, ReceiptUploadResponse } from '../types/receipt'
import type { Expense } from '../types/expense'

export async function uploadReceipt(file: File, expenseId?: string): Promise<ReceiptUploadResponse> {
  try {
    const formData = new FormData()
    formData.append('file', file)
    if (expenseId) formData.append('expense_id', expenseId)
    const response = await apiClient.post<ReceiptUploadResponse>('/receipts/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return response.data
  } catch (error) {
    throw toApiError(error)
  }
}

export async function confirmReceipt(input: ReceiptConfirmInput): Promise<Expense> {
  try {
    const response = await apiClient.post<Expense>('/receipts/confirm', input)
    return response.data
  } catch (error) {
    throw toApiError(error)
  }
}
