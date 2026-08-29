import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'

import { ExpenseForm } from '../components/ExpenseForm'
import { ReceiptDropzone } from '../components/ReceiptDropzone'
import { LoadingState } from '../components/StatusStates'
import { uploadReceipt, confirmReceipt } from '../services/receiptService'
import { toApiError } from '../services/apiClient'
import type { ExpenseFormInput, ExpenseFormValues } from '../schemas/expense'
import type { ExtractedReceiptData, ReceiptUploadResponse } from '../types/receipt'
import { todayIsoDate } from '../lib/format'

function extractedToFormValues(data: ExtractedReceiptData | null): Partial<ExpenseFormInput> {
  if (!data) return {}
  return {
    business_name: data.business_name ?? '',
    receipt_number: data.receipt_number ?? '',
    amount: data.total ?? 0,
    vat_amount: data.vat ?? '',
    currency: data.currency || 'ILS',
    category: data.category,
    expense_date: data.date ?? todayIsoDate(),
  }
}

/** Maps a known API error status to a translation key for a clearer user-facing message. */
function confirmErrorKey(status: number | undefined): string | null {
  if (status === 409) return 'uploadReceipt.errors.alreadyConfirmed'
  if (status === 410) return 'uploadReceipt.errors.uploadExpired'
  if (status === 404) return 'uploadReceipt.errors.uploadNotFound'
  return null
}

export function UploadReceiptPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [file, setFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [uploadResult, setUploadResult] = useState<ReceiptUploadResponse | null>(null)
  const [showSuccess, setShowSuccess] = useState(false)

  useEffect(() => {
    if (!file) {
      setPreviewUrl(null)
      return
    }
    const objectUrl = URL.createObjectURL(file)
    setPreviewUrl(objectUrl)
    return () => URL.revokeObjectURL(objectUrl)
  }, [file])

  const uploadMutation = useMutation({
    mutationFn: uploadReceipt,
    onSuccess: (result) => setUploadResult(result),
  })

  const confirmMutation = useMutation({
    mutationFn: confirmReceipt,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['expenses'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] })
      setShowSuccess(true)
      setTimeout(() => navigate('/expenses'), 900)
    },
  })

  function handleFileSelected(selectedFile: File) {
    if (uploadMutation.isPending) return
    setFile(selectedFile)
    setUploadResult(null)
    uploadMutation.mutate(selectedFile)
  }

  function handleConfirm(values: ExpenseFormValues) {
    if (!uploadResult || confirmMutation.isPending) return
    confirmMutation.mutate({
      upload_id: uploadResult.upload_id,
      business_name: values.business_name,
      receipt_number: values.receipt_number || null,
      amount: Number(values.amount),
      vat_amount: values.vat_amount === '' ? null : Number(values.vat_amount),
      currency: values.currency,
      category: values.category,
      expense_date: values.expense_date,
      payment_method: values.payment_method || null,
      notes: values.notes || null,
      extraction_confidence: uploadResult.extracted_data?.confidence ?? null,
    })
  }

  const confidence = uploadResult?.extracted_data?.confidence
  const warnings = uploadResult?.extracted_data?.warnings ?? []
  const confirmError = confirmMutation.isError ? toApiError(confirmMutation.error) : null
  const confirmErrorTranslationKey = confirmError ? confirmErrorKey(confirmError.status) : null

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">{t('uploadReceipt.title')}</h1>
        <p className="mt-1 text-sm text-slate-500">{t('uploadReceipt.subtitle')}</p>
      </div>

      {showSuccess && (
        <div
          role="status"
          className="rounded-lg border border-success-500/30 bg-success-50 p-3 text-sm text-success-700"
        >
          {t('uploadReceipt.successMessage')}
        </div>
      )}

      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <ReceiptDropzone onFileSelected={handleFileSelected} previewUrl={previewUrl} />
      </div>

      {uploadMutation.isPending && <LoadingState label={t('uploadReceipt.analyzing')} />}

      {uploadMutation.isError && (
        <div role="alert" className="rounded-lg border border-danger-500/30 bg-danger-50 p-4 text-sm text-danger-700">
          <p className="font-semibold">{t('uploadReceipt.uploadFailedTitle')}</p>
          <p className="mt-1">{toApiError(uploadMutation.error).message}</p>
        </div>
      )}

      {uploadResult && !uploadResult.extraction_succeeded && (
        <div className="rounded-lg border border-amber-400/40 bg-amber-50 p-4 text-sm text-amber-800">
          <p className="font-semibold">{t('uploadReceipt.extractionFailedTitle')}</p>
          <p className="mt-1">{t('uploadReceipt.extractionFailedBody')}</p>
        </div>
      )}

      {uploadResult && (
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-base font-semibold text-slate-900">{t('uploadReceipt.reviewAndConfirm')}</h2>
            {typeof confidence === 'number' && (
              <span className="rounded-full bg-brand-50 px-2.5 py-0.5 text-xs font-medium text-brand-700">
                {t('uploadReceipt.confidence', { value: Math.round(confidence * 100) })}
              </span>
            )}
          </div>

          {warnings.length > 0 && (
            <ul className="mb-4 space-y-1 rounded-lg border border-amber-400/40 bg-amber-50 p-3 text-xs text-amber-800">
              {warnings.map((warning) => (
                <li key={warning}>⚠ {t(`uploadReceipt.warnings.${warning}`, warning)}</li>
              ))}
            </ul>
          )}

          {confirmError && (
            <div
              role="alert"
              className="mb-4 rounded-lg border border-danger-500/30 bg-danger-50 p-3 text-sm text-danger-700"
            >
              <p>{confirmErrorTranslationKey ? t(confirmErrorTranslationKey) : confirmError.message}</p>
              {confirmErrorTranslationKey === 'uploadReceipt.errors.alreadyConfirmed' && (
                <Link to="/expenses" className="mt-1 inline-block font-medium underline">
                  {t('dashboard.viewAll')}
                </Link>
              )}
            </div>
          )}

          <ExpenseForm
            key={uploadResult.upload_id}
            defaultValues={extractedToFormValues(uploadResult.extracted_data)}
            submitLabel={t('uploadReceipt.confirmAndSave')}
            isSubmitting={confirmMutation.isPending}
            onSubmit={handleConfirm}
          />
        </div>
      )}
    </div>
  )
}
