import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'

import { ExtractionModeBadge } from '../components/ExtractionModeBadge'
import { ReceiptDropzone } from '../components/ReceiptDropzone'
import { LoadingState, EmptyState } from '../components/StatusStates'
import { importHistoricalDocument } from '../services/documentService'
import { getSale } from '../services/saleService'
import { getSystemCapabilities } from '../services/systemService'
import { toApiError } from '../services/apiClient'
import { formatCurrency, formatDate } from '../lib/format'
import { groupWarnings, type WarningGroup } from '../lib/warnings'

const WARNING_GROUP_STYLES: Record<WarningGroup, string> = {
  recovered: 'border-sky-400/40 bg-sky-50 text-sky-800 dark:bg-sky-500/10 dark:text-sky-300',
  review: 'border-amber-400/40 bg-amber-50 text-amber-800 dark:bg-amber-500/10 dark:text-amber-300',
  attention: 'border-zinc-300 bg-zinc-50 text-zinc-600 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-400',
}

export function ImportDocumentPage() {
  const { t, i18n } = useTranslation()
  const [searchParams] = useSearchParams()
  const saleId = searchParams.get('saleId')
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const queryClient = useQueryClient()

  const { data: sale, isLoading: isLoadingSale } = useQuery({
    queryKey: ['sale', saleId],
    queryFn: () => getSale(saleId!),
    enabled: !!saleId,
  })

  const importMutation = useMutation({
    mutationFn: (file: File) => importHistoricalDocument(saleId!, file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sale', saleId] })
      queryClient.invalidateQueries({ queryKey: ['sales'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] })
      queryClient.invalidateQueries({ queryKey: ['exception-center'] })
    },
  })

  const { data: capabilities } = useQuery({
    queryKey: ['system-capabilities'],
    queryFn: getSystemCapabilities,
    staleTime: Infinity,
    retry: 1,
  })
  const showOllamaUnavailableWarning =
    capabilities?.receipt_extraction_mode === 'local' && capabilities.ollama_available === false

  function handleFileSelected(file: File) {
    if (importMutation.isPending) return
    setPreviewUrl(URL.createObjectURL(file))
    importMutation.mutate(file)
  }

  if (!saleId) {
    return (
      <div className="max-w-2xl">
        <EmptyState title={t('importDocument.noSaleTitle')} description={t('importDocument.noSaleDescription')} />
      </div>
    )
  }

  const warningGroups = groupWarnings(importMutation.data?.extracted_data?.warnings ?? [])

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100">{t('importDocument.title')}</h1>
          <ExtractionModeBadge />
        </div>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">{t('importDocument.subtitle')}</p>
      </div>

      {isLoadingSale && <LoadingState label={t('common.loading')} />}

      {sale && (
        <div className="rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
          <p className="text-xs font-medium text-zinc-500 dark:text-zinc-400">{t('importDocument.targetSaleLabel')}</p>
          <div className="mt-1 flex items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="truncate font-medium text-zinc-900 dark:text-zinc-100">{sale.customer_name}</p>
              <p className="text-xs text-zinc-500 dark:text-zinc-400">
                {formatDate(sale.occurred_at.slice(0, 10), i18n.language)} · {sale.service_name}
              </p>
            </div>
            <p className="font-medium tabular-nums text-zinc-900 dark:text-zinc-100">
              {formatCurrency(sale.gross_amount, sale.currency, i18n.language)}
            </p>
          </div>
        </div>
      )}

      {showOllamaUnavailableWarning && (
        <div
          role="alert"
          className="rounded-lg border border-amber-400/40 bg-amber-50 p-4 text-sm text-amber-800 dark:bg-amber-500/10 dark:text-amber-300"
        >
          {t('uploadReceipt.errors.ollamaUnavailable')}
        </div>
      )}

      <div className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
        <ReceiptDropzone onFileSelected={handleFileSelected} previewUrl={previewUrl} />
      </div>

      {importMutation.isPending && <LoadingState label={t('importDocument.importing')} />}

      {importMutation.isError && (
        <div role="alert" className="rounded-lg border border-danger-500/30 bg-danger-50 p-4 text-sm text-danger-700 dark:bg-danger-500/10 dark:text-danger-400">
          <p className="font-semibold">{t('importDocument.importFailedTitle')}</p>
          <p className="mt-1">{toApiError(importMutation.error).message}</p>
        </div>
      )}

      {importMutation.data && (
        <div className="rounded-2xl border border-success-500/30 bg-success-50 p-4 text-sm text-success-700 dark:bg-success-500/10 dark:text-success-400">
          <p className="font-semibold">{t('importDocument.attachedTitle')}</p>
          <p className="mt-1">{t('importDocument.attachedBody')}</p>
          {!importMutation.data.extraction_succeeded && (
            <p className="mt-2 text-xs">{t('importDocument.extractionFailedNote')}</p>
          )}
          {(['review', 'attention', 'recovered'] as const).map((group) =>
            warningGroups[group].length > 0 ? (
              <div key={group} className={`mt-3 rounded-lg border p-3 text-xs ${WARNING_GROUP_STYLES[group]}`}>
                <p className="mb-1 font-semibold">{t(`uploadReceipt.warningGroups.${group}`)}</p>
                <ul className="space-y-1">
                  {warningGroups[group].map((warning) => (
                    <li key={warning}>{t(`uploadReceipt.warnings.${warning}`, t('uploadReceipt.warnings.extraction_incomplete'))}</li>
                  ))}
                </ul>
              </div>
            ) : null,
          )}
          <Link to="/sales" className="mt-3 inline-block font-medium underline">
            {t('dashboard.viewAll')}
          </Link>
        </div>
      )}
    </div>
  )
}
