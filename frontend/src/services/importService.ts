import { apiClient, toApiError } from './apiClient'
import type { CsvConfirmResponse, CsvPreviewResponse, CsvPreviewRow } from '../types/imports'

export async function previewCsv(file: File): Promise<CsvPreviewResponse> {
  try {
    const formData = new FormData()
    formData.append('file', file)
    const response = await apiClient.post<CsvPreviewResponse>('/imports/csv/preview', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return response.data
  } catch (error) {
    throw toApiError(error)
  }
}

export async function confirmCsvImport(
  fileHash: string,
  filename: string | null,
  validRows: CsvPreviewRow[],
): Promise<CsvConfirmResponse> {
  try {
    const response = await apiClient.post<CsvConfirmResponse>('/imports/csv/confirm', {
      file_hash: fileHash,
      filename,
      valid_rows: validRows,
    })
    return response.data
  } catch (error) {
    throw toApiError(error)
  }
}
