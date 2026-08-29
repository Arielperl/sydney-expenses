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
        <h1 className="text-2xl font-semibold text-slate-900">{t('dashboard.title')}</h1>
        <p className="mt-1 text-sm text-slate-500">{t('dashboard.subtitle')}</p>
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
                className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
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

          {data.totals_by_category.length > 0 && (
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="text-base font-semibold text-slate-900">{t('dashboard.spendingByCategory')}</h2>
              <p className="text-sm text-slate-500">{t('dashboard.currentMonth')}</p>
              <div className="mt-4">
                <CategoryChart data={data.totals_by_category} currency={currency} />
              </div>
            </div>
          )}

          <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
            <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
              <h2 className="text-base font-semibold text-slate-900">{t('dashboard.recentExpenses')}</h2>
              <Link to="/expenses" className="text-sm font-medium text-brand-600 hover:text-brand-700">
                {t('dashboard.viewAll')}
              </Link>
            </div>
            <ul className="divide-y divide-slate-100">
              {data.recent_expenses.map((expense) => (
                <li key={expense.id} className="flex items-center justify-between gap-4 px-5 py-3">
                  <div className="min-w-0">
                    <p className="truncate font-medium text-slate-900">{expense.business_name}</p>
                    <p className="text-xs text-slate-500">{formatDate(expense.expense_date, i18n.language)}</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <CategoryBadge category={expense.category} />
                    <span className="font-medium text-slate-900">
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
