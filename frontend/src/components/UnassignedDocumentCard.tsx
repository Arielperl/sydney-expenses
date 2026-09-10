import { useTranslation } from 'react-i18next'

import { formatCurrency, formatDateTime } from '../lib/format'
import type { UnassignedDocument } from '../types/reconciliation'

export function UnassignedDocumentCard({
  document,
  onRematch,
  onChooseTransaction,
  onCreateExpense,
  onDiscard,
  isRematching = false,
}: {
  document: UnassignedDocument
  onRematch: () => void
  onChooseTransaction: () => void
  onCreateExpense: () => void
  onDiscard: () => void
  isRematching?: boolean
}) {
  const { t, i18n } = useTranslation()

  return (
    <div className="rounded-2xl border border-stone-200 bg-white p-4 shadow-sm dark:border-stone-800 dark:bg-stone-900">
      <div className="flex items-start gap-3">
        {document.preview_url && (
          <img
            src={document.preview_url}
            alt={t('reconciliation.receiptPreviewAlt')}
            className="h-16 w-16 shrink-0 rounded-md border border-stone-200 object-cover dark:border-stone-700"
          />
        )}
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <p className="truncate font-medium text-stone-900 dark:text-stone-100">
                {document.extracted_business_name ?? t('reconciliation.document.noBusinessName')}
              </p>
              <p className="text-xs text-stone-500 dark:text-stone-400">
                {t('reconciliation.document.receivedAt', {
                  time: formatDateTime(document.received_at, i18n.language),
                })}
              </p>
            </div>
            {document.extracted_total != null && (
              <p className="shrink-0 font-medium tabular-nums text-stone-900 dark:text-stone-100">
                {formatCurrency(document.extracted_total, document.extracted_currency ?? 'ILS', i18n.language)}
              </p>
            )}
          </div>

          <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-xs text-stone-500 dark:text-stone-400">
            {document.extracted_date && (
              <div>
                <dt className="inline font-medium">{t('form.expenseDate')}: </dt>
                <dd className="inline">{document.extracted_date}</dd>
              </div>
            )}
            {document.extracted_receipt_number && (
              <div>
                <dt className="inline font-medium">{t('form.receiptNumber')}: </dt>
                <dd className="inline">{document.extracted_receipt_number}</dd>
              </div>
            )}
            {document.extracted_vat != null && (
              <div>
                <dt className="inline font-medium">{t('form.vatAmount')}: </dt>
                <dd className="inline">
                  {formatCurrency(document.extracted_vat, document.extracted_currency ?? 'ILS', i18n.language)}
                </dd>
              </div>
            )}
          </dl>

          {document.extraction_warnings.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {document.extraction_warnings.map((warning) => (
                <span
                  key={warning}
                  className="rounded-full bg-amber-50 px-2 py-0.5 text-xs text-amber-800 dark:bg-amber-500/10 dark:text-amber-300"
                >
                  {t(`uploadReceipt.warnings.${warning}`, warning)}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="mt-3 flex flex-wrap justify-end gap-2">
        <button
          type="button"
          onClick={onDiscard}
          className="rounded-md border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 hover:bg-stone-50 dark:border-stone-700 dark:text-stone-200 dark:hover:bg-stone-800"
        >
          {t('reconciliation.document.discard')}
        </button>
        <button
          type="button"
          onClick={onCreateExpense}
          className="rounded-md border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 hover:bg-stone-50 dark:border-stone-700 dark:text-stone-200 dark:hover:bg-stone-800"
        >
          {t('reconciliation.document.createExpense')}
        </button>
        <button
          type="button"
          onClick={onChooseTransaction}
          className="rounded-md border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 hover:bg-stone-50 dark:border-stone-700 dark:text-stone-200 dark:hover:bg-stone-800"
        >
          {t('reconciliation.document.chooseTransaction')}
        </button>
        <button
          type="button"
          onClick={onRematch}
          disabled={isRematching}
          className="rounded-md bg-brand-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
        >
          {isRematching ? t('reconciliation.document.rematching') : t('reconciliation.document.rematch')}
        </button>
      </div>
    </div>
  )
}
