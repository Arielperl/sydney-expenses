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
import { formatDate } from '../lib/format'
import { Money } from '../components/Money'
import { PageHeader } from '../components/ui'
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

  const { data: sale, isPending: isLoadingSale } = useQuery({
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
      <PageHeader title={t('importDocument.title')} description={t('importDocument.subtitle')} actions={<ExtractionModeBadge />} />

      {isLoadingSale && <LoadingState label={t('common.loading')} />}

      {sale && (
        <div className="rounded-xl border border-zinc-200/80 bg-white p-4 shadow-card dark:border-zinc-800 dark:bg-zinc-900">
          <p className="text-xs font-medium text-zinc-500 dark:text-zinc-400">{t('importDocument.targetSaleLabel')}</p>
          <div className="mt-1 flex items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="truncate font-medium text-zinc-900 dark:text-zinc-100" title={sale.customer_name}>{sale.customer_name}</p>
              <p className="mt-0.5 text-xs text-zinc-500 dark:text-zinc-400">
                <bdi>{formatDate(sale.occurred_at.slice(0, 10), i18n.language)}</bdi> · {sale.service_name}
              </p>
            </div>
            <p className="shrink-0 font-medium text-zinc-900 dark:text-zinc-100">
              <Money amount={sale.gross_amount} currency={sale.currency} />
            </p>
          </div>
        </div>
      )}

      {showOllamaUnavailableWarning && (
        <div
          role="alert"
          className="rounded-xl border border-amber-600/20 bg-amber-50 p-4 text-sm text-amber-900 dark:border-amber-500/25 dark:bg-amber-500/10 dark:text-amber-200"
        >
          {t('uploadReceipt.errors.ollamaUnavailable')}
        </div>
      )}

      <div className="rounded-xl border border-zinc-200/80 bg-white p-6 shadow-card dark:border-zinc-800 dark:bg-zinc-900">
        <ReceiptDropzone onFileSelected={handleFileSelected} previewUrl={previewUrl} />
      </div>

      {importMutation.isPending && <LoadingState label={t('importDocument.importing')} />}

      {importMutation.isError && (
        <div role="alert" className="rounded-xl border border-danger-600/20 bg-danger-50 p-4 text-sm text-danger-700 dark:bg-danger-500/10 dark:text-danger-500">
          <p className="font-semibold">{t('importDocument.importFailedTitle')}</p>
          <p className="mt-1">{toApiError(importMutation.error).message}</p>
        </div>
      )}

      {importMutation.data && (
        <div className="rounded-xl border border-success-500/25 bg-success-50 p-4 text-sm text-success-700 dark:bg-success-500/10 dark:text-success-500">
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
