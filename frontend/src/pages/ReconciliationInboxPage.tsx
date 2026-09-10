import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { DocumentStatusBadge } from '../components/DocumentStatusBadge'
import { MatchSuggestionCard } from '../components/MatchSuggestionCard'
import { ErrorState, LoadingState } from '../components/StatusStates'
import { formatCurrency, formatDate } from '../lib/format'
import { toApiError } from '../services/apiClient'
import { approveMatch, getReconciliationInbox, rejectMatch } from '../services/reconciliationService'
import type { Expense } from '../types/expense'

function TransactionRow({ expense }: { expense: Expense }) {
  const { i18n } = useTranslation()
  return (
    <li className="flex items-center justify-between gap-4 px-4 py-3">
      <div className="min-w-0">
        <p className="truncate font-medium text-stone-900 dark:text-stone-100">{expense.business_name}</p>
        <p className="text-xs text-stone-500 dark:text-stone-400">{formatDate(expense.expense_date, i18n.language)}</p>
      </div>
      <div className="flex items-center gap-3">
        <DocumentStatusBadge status={expense.document_status} />
        <span className="font-medium tabular-nums text-stone-900 dark:text-stone-100">
          {formatCurrency(expense.amount, expense.currency, i18n.language)}
        </span>
      </div>
    </li>
  )
}

function ExpenseListSection({
  title,
  emptyLabel,
  expenses,
}: {
  title: string
  emptyLabel: string
  expenses: Expense[]
}) {
  return (
    <section>
      <h2 className="text-base font-semibold text-stone-900 dark:text-stone-100">{title}</h2>
      {expenses.length === 0 ? (
        <p className="mt-2 text-sm text-stone-500 dark:text-stone-400">{emptyLabel}</p>
      ) : (
        <ul className="mt-3 divide-y divide-stone-100 rounded-2xl border border-stone-200 bg-white dark:divide-stone-800 dark:border-stone-800 dark:bg-stone-900">
          {expenses.map((expense) => (
            <TransactionRow key={expense.id} expense={expense} />
          ))}
        </ul>
      )}
    </section>
  )
}

export function ReconciliationInboxPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['reconciliation-inbox'],
    queryFn: getReconciliationInbox,
  })

  const approveMutation = useMutation({
    mutationFn: (expenseId: string) => approveMatch(expenseId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reconciliation-inbox'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] })
    },
  })
  const rejectMutation = useMutation({
    mutationFn: (expenseId: string) => rejectMatch(expenseId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reconciliation-inbox'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] })
    },
  })

  if (isLoading) return <LoadingState label={t('common.loading')} />
  if (isError) return <ErrorState message={toApiError(error).message} onRetry={() => refetch()} />
  if (!data) return null

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold text-stone-900 dark:text-stone-100">{t('reconciliation.title')}</h1>
        <p className="mt-1 text-sm text-stone-500 dark:text-stone-400">{t('reconciliation.subtitle')}</p>
      </div>

      <section>
        <h2 className="text-base font-semibold text-stone-900 dark:text-stone-100">
          {t('reconciliation.sections.suggestedMatches')}
        </h2>
        {data.suggested_matches.length === 0 ? (
          <p className="mt-2 text-sm text-stone-500 dark:text-stone-400">{t('reconciliation.emptySuggestedMatches')}</p>
        ) : (
          <div className="mt-3 space-y-3">
            {data.suggested_matches.map((expense) => (
              <MatchSuggestionCard
                key={expense.id}
                expense={expense}
                onApprove={() => approveMutation.mutate(expense.id)}
                onReject={() => rejectMutation.mutate(expense.id)}
                isApproving={approveMutation.isPending && approveMutation.variables === expense.id}
                isRejecting={rejectMutation.isPending && rejectMutation.variables === expense.id}
              />
            ))}
          </div>
        )}
      </section>

      <ExpenseListSection
        title={t('reconciliation.sections.missingDocuments')}
        emptyLabel={t('reconciliation.emptyMissingDocuments')}
        expenses={data.missing_documents}
      />

      <ExpenseListSection
        title={t('reconciliation.sections.documentsWithoutTransactions')}
        emptyLabel={t('reconciliation.emptyDocumentsWithoutTransactions')}
        expenses={data.documents_without_transactions}
      />

      <ExpenseListSection
        title={t('reconciliation.sections.recentlyCompleted')}
        emptyLabel={t('reconciliation.emptyRecentlyCompleted')}
        expenses={data.recently_completed}
      />
    </div>
  )
}
