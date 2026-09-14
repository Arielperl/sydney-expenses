export interface CsvRowError {
  row_number: number
  message: string
}

export interface CsvPreviewRow {
  row_number: number
  sale_date: string
  customer: string
  service: string
  amount: number | string
  currency: string
  external_id: string
}

export interface CsvPreviewResponse {
  file_hash: string
  filename: string | null
  valid_rows: CsvPreviewRow[]
  errors: CsvRowError[]
  is_repeat_file: boolean
  preview_signature: string
  preview_expires_at: number
}

export interface CsvConfirmResponse {
  import_batch_id: string
  created_count: number
  duplicate_count: number
  error_count: number
}
