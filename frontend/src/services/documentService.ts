import { apiClient, toApiError } from './apiClient'
import type { DocumentImportResponse } from '../types/document'

export async function importHistoricalDocument(saleId: string, file: File): Promise<DocumentImportResponse> {
  try {
    const formData = new FormData()
    formData.append('file', file)
    const response = await apiClient.post<DocumentImportResponse>('/documents/import', formData, {
      params: { sale_id: saleId },
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return response.data
  } catch (error) {
    throw toApiError(error)
  }
}
