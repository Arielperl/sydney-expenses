import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { Modal } from './Modal'
import { LoadingState, ErrorState, EmptyState } from './StatusStates'
import { formatCurrency, formatDate } from '../lib/format'
import { toApiError } from '../services/apiClient'
import { listEligibleExpenses } from '../services/reconciliationService'
import type { UnassignedDocument } from '../types/reconciliation'

export function ManualMatchDialog({
  document,
  onClose,
  onConfirm,
  isConfirming = false,
  confirmingExpenseId,
}: {
  document: UnassignedDocument
  onClose: () => void
  onConfirm: (expenseId: string) => void
  isConfirming?: boolean
  confirmingExpenseId?: string | null
}) {
  const { t, i18n } = useTranslation()
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['eligible-expenses', document.id],
    queryFn: () => listEligibleExpenses(document.id),
  })

  return (
    <Modal title={t('reconciliation.manualMatch.title')} onClose={onClose}>
      {isLoading && <LoadingState label={t('common.loading')} />}
      {isError && <ErrorState message={toApiError(error).message} onRetry={() => refetch()} />}
      {!isLoading && !isError && data && data.length === 0 && (
        <EmptyState title={t('reconciliation.manualMatch.empty')} />
      )}
      {!isLoading && !isError && data && data.length > 0 && (
        <ul className="max-h-96 space-y-2 overflow-y-auto">
          {data.map((candidate) => (
            <li
              key={candidate.expense.id}
              className="rounded-lg border border-stone-200 p-3 dark:border-stone-800"
            >
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate font-medium text-stone-900 dark:text-stone-100">
                    {candidate.expense.business_name}
                  </p>
                  <p className="text-xs text-stone-500 dark:text-stone-400">
                    {formatDate(candidate.expense.expense_date, i18n.language)}
                  </p>
                </div>
                <p className="shrink-0 font-medium tabular-nums text-stone-900 dark:text-stone-100">
                  {formatCurrency(candidate.expense.amount, candidate.expense.currency, i18n.language)}
                </p>
              </div>
              {candidate.has_conflict && (
                <p className="mt-1.5 text-xs text-amber-700 dark:text-amber-400">
                  {t('reconciliation.manualMatch.conflictWarning')}
                </p>
              )}
              <div className="mt-2 flex justify-end">
                <button
                  type="button"
                  onClick={() => onConfirm(candidate.expense.id)}
                  disabled={isConfirming}
                  className="rounded-md bg-brand-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
                >
                  {isConfirming && confirmingExpenseId === candidate.expense.id
                    ? t('reconciliation.manualMatch.confirming')
                    : t('reconciliation.manualMatch.confirm')}
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Modal>
  )
}
