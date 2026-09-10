import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { StatCard } from '../components/StatCard'
import { CategoryChart } from '../components/CategoryChart'
import { EmptyState, ErrorState, LoadingState } from '../components/StatusStates'
import { CategoryBadge } from '../components/CategoryBadge'
import { getDashboardStats } from '../services/dashboardService'
import { formatCurrency, formatDate } from '../lib/format'
import { toApiError } from '../services/apiClient'

function CountStat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm dark:border-stone-800 dark:bg-stone-900">
      <p className="text-sm font-medium text-stone-500 dark:text-stone-400">{label}</p>
      <p className="mt-2 text-3xl font-semibold tracking-tight tabular-nums text-stone-900 dark:text-stone-100">
        {value}
      </p>
    </div>
  )
}

export function DashboardPage() {
  const { t, i18n } = useTranslation()
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: getDashboardStats,
  })

  if (isLoading) return <LoadingState label={t('common.loading')} />

  if (isError) {
    return <ErrorState message={toApiError(error).message} onRetry={() => refetch()} />
  }

  if (!data) return null

  const hasAnyExpenses = data.recent_expenses.length > 0 || data.totals_by_category.length > 0
  const currency = data.recent_expenses[0]?.currency ?? 'ILS'

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold text-stone-900 dark:text-stone-100">{t('dashboard.title')}</h1>
        <p className="mt-1 text-sm text-stone-500 dark:text-stone-400">{t('dashboard.subtitle')}</p>
      </div>

      {!hasAnyExpenses ? (
        <EmptyState
          title={t('dashboard.emptyTitle')}
          description={t('dashboard.emptyDescription')}
          action={
            <div className="flex justify-center gap-3">
              <Link
                to="/add-expense"
                className="rounded-md bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700"
              >
                {t('nav.addExpense')}
              </Link>
              <Link
                to="/upload-receipt"
                className="rounded-md border border-stone-300 bg-white px-4 py-2 text-sm font-semibold text-stone-700 hover:bg-stone-50 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-200 dark:hover:bg-stone-700"
              >
                {t('nav.uploadReceipt')}
              </Link>
            </div>
          }
        />
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <StatCard
              label={t('dashboard.thisMonth')}
              amount={data.current_month_total}
              currency={currency}
              changePercent={data.percentage_change}
            />
            <StatCard label={t('dashboard.lastMonth')} amount={data.previous_month_total} currency={currency} />
          </div>

          <div>
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold text-stone-900 dark:text-stone-100">
                {t('dashboard.reconciliationOverview')}
              </h2>
              <Link
                to="/reconciliation"
                className="text-sm font-medium text-brand-600 hover:text-brand-700 dark:text-brand-400 dark:hover:text-brand-300"
              >
                {t('dashboard.viewAll')}
              </Link>
            </div>
            <div className="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-3">
              <StatCard
                label={t('dashboard.missingDocuments', { count: data.missing_documents_count })}
                amount={data.missing_documents_total}
                currency={currency}
              />
              <CountStat
                label={t('dashboard.matchesAwaitingConfirmation')}
                value={data.matches_awaiting_confirmation_count}
              />
              <CountStat
                label={t('dashboard.documentAttachmentRate')}
                value={data.document_attachment_rate != null ? `${data.document_attachment_rate}%` : '—'}
              />
            </div>
          </div>

          {data.totals_by_category.length > 0 && (
            <div className="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm dark:border-stone-800 dark:bg-stone-900">
              <h2 className="text-base font-semibold text-stone-900 dark:text-stone-100">{t('dashboard.spendingByCategory')}</h2>
              <p className="text-sm text-stone-500 dark:text-stone-400">{t('dashboard.currentMonth')}</p>
              <div className="mt-4">
                <CategoryChart data={data.totals_by_category} currency={currency} />
              </div>
            </div>
          )}

          <div className="rounded-2xl border border-stone-200 bg-white shadow-sm dark:border-stone-800 dark:bg-stone-900">
            <div className="flex items-center justify-between border-b border-stone-100 px-5 py-4 dark:border-stone-800">
              <h2 className="text-base font-semibold text-stone-900 dark:text-stone-100">{t('dashboard.recentExpenses')}</h2>
              <Link to="/expenses" className="text-sm font-medium text-brand-600 hover:text-brand-700 dark:text-brand-400 dark:hover:text-brand-300">
                {t('dashboard.viewAll')}
              </Link>
            </div>
            <ul className="divide-y divide-stone-100 dark:divide-stone-800">
              {data.recent_expenses.map((expense) => (
                <li key={expense.id} className="flex items-center justify-between gap-4 px-5 py-3">
                  <div className="min-w-0">
                    <p className="truncate font-medium text-stone-900 dark:text-stone-100">{expense.business_name}</p>
                    <p className="text-xs text-stone-500 dark:text-stone-400">
                      {formatDate(expense.expense_date, i18n.language)} · {t(`expenseSource.${expense.source}`)}
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <CategoryBadge category={expense.category} />
                    <span className="font-medium tabular-nums text-stone-900 dark:text-stone-100">
                      {formatCurrency(expense.amount, expense.currency, i18n.language)}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </>
      )}
    </div>
  )
}
