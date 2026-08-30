import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'

import { ExpenseForm } from '../components/ExpenseForm'
import { ExtractionModeBadge } from '../components/ExtractionModeBadge'
import { ReceiptDropzone } from '../components/ReceiptDropzone'
import { LoadingState } from '../components/StatusStates'
import { uploadReceipt, confirmReceipt } from '../services/receiptService'
import { getSystemCapabilities } from '../services/systemService'
import { toApiError } from '../services/apiClient'
import type { ExpenseFormInput, ExpenseFormValues } from '../schemas/expense'
import type { ExtractedReceiptData, ReceiptUploadResponse } from '../types/receipt'
import { groupWarnings, type WarningGroup } from '../lib/warnings'

// Below this quality-score threshold, so little was extracted that showing
// the ordinary "review and confirm" heading (with a near-0% badge) next to
// an almost entirely empty form would read as if something went wrong with
// the form itself, rather than "we just couldn't read this receipt well".
const INSUFFICIENT_EXTRACTION_THRESHOLD = 0.15

const WARNING_GROUP_STYLES: Record<WarningGroup, string> = {
  recovered: 'border-sky-400/40 bg-sky-50 text-sky-800',
  review: 'border-amber-400/40 bg-amber-50 text-amber-800',
  attention: 'border-slate-300 bg-slate-50 text-slate-600',
}

// An unrecognized amount/date must never be silently replaced with 0 or
// today's date — either would look like a real extracted value instead of
// the "we couldn't read this" signal it actually is. Leaving the field
// empty forces the (already-required) form validation to visibly prompt the
// user for it, instead of letting a wrong guess slip through unnoticed.
function extractedToFormValues(data: ExtractedReceiptData | null): Partial<ExpenseFormInput> {
  if (!data) return {}
  return {
    business_name: data.business_name ?? '',
    receipt_number: data.receipt_number ?? '',
    amount: data.total ?? '',
    vat_amount: data.vat ?? '',
    currency: data.currency || 'ILS',
    category: data.category,
    expense_date: data.date ?? '',
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
  const warningGroups = groupWarnings(uploadResult?.extracted_data?.warnings ?? [])
  const isInsufficientExtraction =
    uploadResult?.extraction_succeeded === true &&
    typeof confidence === 'number' &&
    confidence < INSUFFICIENT_EXTRACTION_THRESHOLD
  const confirmError = confirmMutation.isError ? toApiError(confirmMutation.error) : null
  const confirmErrorTranslationKey = confirmError ? confirmErrorKey(confirmError.status) : null

  const { data: capabilities } = useQuery({
    queryKey: ['system-capabilities'],
    queryFn: getSystemCapabilities,
    staleTime: Infinity,
    retry: 1,
  })
  const showOllamaUnavailableWarning =
    capabilities?.receipt_extraction_mode === 'local' && capabilities.ollama_available === false

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h1 className="text-2xl font-semibold text-slate-900">{t('uploadReceipt.title')}</h1>
          <ExtractionModeBadge />
        </div>
        <p className="mt-1 text-sm text-slate-500">{t('uploadReceipt.subtitle')}</p>
      </div>

      {showOllamaUnavailableWarning && (
        <div
          role="alert"
          className="rounded-lg border border-amber-400/40 bg-amber-50 p-4 text-sm text-amber-800"
        >
          {t('uploadReceipt.errors.ollamaUnavailable')}
        </div>
      )}

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

      {uploadResult && uploadResult.extraction_succeeded && isInsufficientExtraction && (
        <div className="rounded-lg border border-amber-400/40 bg-amber-50 p-4 text-sm text-amber-800">
          <p className="font-semibold">{t('uploadReceipt.insufficientExtractionTitle')}</p>
          <p className="mt-1">{t('uploadReceipt.insufficientExtractionBody')}</p>
        </div>
      )}

      {uploadResult && (
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-base font-semibold text-slate-900">{t('uploadReceipt.reviewAndConfirm')}</h2>
            {typeof confidence === 'number' && !isInsufficientExtraction && (
              <span
                className="rounded-full bg-brand-50 px-2.5 py-0.5 text-xs font-medium text-brand-700"
                title={t('uploadReceipt.qualityScoreExplanation')}
              >
                {t('uploadReceipt.qualityScore', { value: Math.round(confidence * 100) })}
              </span>
            )}
          </div>

          {(['review', 'attention', 'recovered'] as const).map((group) =>
            warningGroups[group].length > 0 ? (
              <div key={group} className={`mb-3 rounded-lg border p-3 text-xs ${WARNING_GROUP_STYLES[group]}`}>
                <p className="mb-1 font-semibold">{t(`uploadReceipt.warningGroups.${group}`)}</p>
                <ul className="space-y-1">
                  {warningGroups[group].map((warning) => (
                    <li key={warning}>
                      {t(`uploadReceipt.warnings.${warning}`, t('uploadReceipt.warnings.extraction_incomplete'))}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null,
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
