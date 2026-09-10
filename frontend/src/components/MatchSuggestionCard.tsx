import { useTranslation } from 'react-i18next'

import { formatCurrency, formatDate } from '../lib/format'
import type { Expense } from '../types/expense'
import type { UnassignedDocument } from '../types/reconciliation'
import { DocumentStatusBadge } from './DocumentStatusBadge'

export function MatchSuggestionCard({
  expense,
  document,
  onApprove,
  onReject,
  isApproving = false,
  isRejecting = false,
}: {
  expense: Expense
  document?: UnassignedDocument | null
  onApprove: () => void
  onReject: () => void
  isApproving?: boolean
  isRejecting?: boolean
}) {
  const { t, i18n } = useTranslation()
  const scorePercent =
    expense.reconciliation_confidence != null ? Math.round(expense.reconciliation_confidence * 100) : null
  const isBusy = isApproving || isRejecting

  return (
    <div className="rounded-2xl border border-stone-200 bg-white p-4 shadow-sm dark:border-stone-800 dark:bg-stone-900">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div className="rounded-lg border border-stone-200 p-3 dark:border-stone-800">
          <p className="text-xs font-medium text-stone-500 dark:text-stone-400">{t('reconciliation.transactionLabel')}</p>
          <div className="mt-1 flex items-start justify-between gap-2">
            <div className="min-w-0">
              <p className="truncate font-medium text-stone-900 dark:text-stone-100">{expense.business_name}</p>
              <p className="text-xs text-stone-500 dark:text-stone-400">
                {formatDate(expense.expense_date, i18n.language)}
              </p>
            </div>
            <div className="shrink-0 text-end">
              <p className="font-medium tabular-nums text-stone-900 dark:text-stone-100">
                {formatCurrency(expense.amount, expense.currency, i18n.language)}
              </p>
              <div className="mt-1 flex items-center justify-end gap-1.5">
                {expense.document_status === 'needs_review' && <DocumentStatusBadge status="needs_review" />}
                {scorePercent != null && (
                  <span className="text-xs text-brand-600 dark:text-brand-400">
                    {t('reconciliation.matchScore', { score: scorePercent })}
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>

        <div className="rounded-lg border border-stone-200 p-3 dark:border-stone-800">
          <p className="text-xs font-medium text-stone-500 dark:text-stone-400">{t('reconciliation.receiptLabel')}</p>
          {document ? (
            <div className="mt-1 flex items-start gap-3">
              {document.preview_url && (
                <img
                  src={document.preview_url}
                  alt={t('reconciliation.receiptPreviewAlt')}
                  className="h-12 w-12 shrink-0 rounded-md border border-stone-200 object-cover dark:border-stone-700"
                />
              )}
              <div className="min-w-0">
                <p className="truncate font-medium text-stone-900 dark:text-stone-100">
                  {document.extracted_business_name ?? '—'}
                </p>
                <p className="text-xs text-stone-500 dark:text-stone-400">
                  {document.extracted_date ? formatDate(document.extracted_date, i18n.language) : '—'}
                </p>
                {document.extracted_total != null && (
                  <p className="mt-0.5 font-medium tabular-nums text-stone-900 dark:text-stone-100">
                    {formatCurrency(document.extracted_total, document.extracted_currency ?? 'ILS', i18n.language)}
                  </p>
                )}
              </div>
            </div>
          ) : (
            <p className="mt-1 text-sm text-stone-500 dark:text-stone-400">{t('reconciliation.noDocumentData')}</p>
          )}
        </div>
      </div>

      {expense.reconciliation_reasons && expense.reconciliation_reasons.length > 0 && (
        <div className="mt-3">
          <p className="text-xs font-medium text-stone-500 dark:text-stone-400">{t('reconciliation.whyMatch')}</p>
          <div className="mt-1 flex flex-wrap gap-1.5">
            {expense.reconciliation_reasons.map((reason) => (
              <span
                key={reason}
                className="rounded-full bg-stone-100 px-2 py-0.5 text-xs text-stone-600 dark:bg-stone-800 dark:text-stone-400"
              >
                {t(`reconciliation.reasons.${reason}`, reason)}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="mt-3 flex justify-end gap-2">
        <button
          type="button"
          onClick={onReject}
          disabled={isBusy}
          className="rounded-md border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 hover:bg-stone-50 disabled:opacity-50 dark:border-stone-700 dark:text-stone-200 dark:hover:bg-stone-800"
        >
          {isRejecting ? t('reconciliation.rejecting') : t('reconciliation.reject')}
        </button>
        <button
          type="button"
          onClick={onApprove}
          disabled={isBusy}
          className="rounded-md bg-brand-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
        >
          {isApproving ? t('reconciliation.approving') : t('reconciliation.approve')}
        </button>
      </div>
    </div>
  )
}
