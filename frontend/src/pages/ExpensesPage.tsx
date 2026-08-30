import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Trans, useTranslation } from 'react-i18next'

import { ExpenseForm } from '../components/ExpenseForm'
import { ExpenseList } from '../components/ExpenseList'
import { Modal } from '../components/Modal'
import { EmptyState, ErrorState, LoadingState } from '../components/StatusStates'
import { inputClasses } from '../components/FormField'
import { deleteExpense, listExpenses, updateExpense } from '../services/expenseService'
import { toApiError } from '../services/apiClient'
import type { ExpenseFormInput, ExpenseFormValues } from '../schemas/expense'
import { EXPENSE_CATEGORIES, type Expense, type ExpenseCategory } from '../types/expense'

function expenseToFormValues(expense: Expense): ExpenseFormInput {
  return {
    business_name: expense.business_name,
    receipt_number: expense.receipt_number ?? '',
    amount: expense.amount,
    vat_amount: expense.vat_amount ?? '',
    currency: expense.currency,
    category: expense.category,
    expense_date: expense.expense_date,
    payment_method: expense.payment_method ?? '',
    notes: expense.notes ?? '',
  }
}

export function ExpensesPage() {
  const { t } = useTranslation()
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState<ExpenseCategory | ''>('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [editingExpense, setEditingExpense] = useState<Expense | null>(null)
  const [deletingExpense, setDeletingExpense] = useState<Expense | null>(null)

  const queryClient = useQueryClient()
  const filters = { search, category, date_from: dateFrom, date_to: dateTo }

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['expenses', filters],
    queryFn: () => listExpenses(filters),
  })

  const updateMutation = useMutation({
    mutationFn: (values: ExpenseFormValues) => {
      if (!editingExpense) throw new Error('No expense selected')
      return updateExpense(editingExpense.id, {
        ...values,
        receipt_number: values.receipt_number || null,
        vat_amount: values.vat_amount === '' ? null : Number(values.vat_amount),
        payment_method: values.payment_method || null,
        notes: values.notes || null,
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['expenses'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] })
      setEditingExpense(null)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteExpense(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['expenses'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] })
      setDeletingExpense(null)
    },
  })

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">{t('expenses.title')}</h1>
        <p className="mt-1 text-sm text-slate-500">{t('expenses.subtitle')}</p>
      </div>

      <div className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:flex-row sm:flex-wrap">
        <div className="min-w-0 sm:flex-[2_2_240px]">
          <label htmlFor="search" className="sr-only">
            {t('expenses.searchLabel')}
          </label>
          <input
            id="search"
            className={inputClasses}
            placeholder={t('expenses.searchPlaceholder')}
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
        <div className="min-w-0 sm:flex-1 sm:basis-40">
          <label htmlFor="category-filter" className="sr-only">
            {t('expenses.categoryFilterLabel')}
          </label>
          <select
            id="category-filter"
            className={inputClasses}
            value={category}
            onChange={(event) => setCategory(event.target.value as ExpenseCategory | '')}
          >
            <option value="">{t('expenses.allCategories')}</option>
            {EXPENSE_CATEGORIES.map((item) => (
              <option key={item} value={item}>
                {t(`categories.${item}`)}
              </option>
            ))}
          </select>
        </div>
        <div className="flex min-w-0 gap-2 sm:flex-1 sm:basis-56">
          <input
            aria-label={t('expenses.dateFromLabel')}
            type="date"
            className={`${inputClasses} min-w-0 flex-1`}
            value={dateFrom}
            onChange={(event) => setDateFrom(event.target.value)}
          />
          <input
            aria-label={t('expenses.dateToLabel')}
            type="date"
            className={`${inputClasses} min-w-0 flex-1`}
            value={dateTo}
            onChange={(event) => setDateTo(event.target.value)}
          />
        </div>
      </div>

      {isLoading && <LoadingState />}
      {isError && <ErrorState message={toApiError(error).message} onRetry={() => refetch()} />}
      {!isLoading && !isError && data && data.length === 0 && (
        <EmptyState title={t('expenses.emptyTitle')} description={t('expenses.emptyDescription')} />
      )}
      {!isLoading && !isError && data && data.length > 0 && (
        <ExpenseList expenses={data} onEdit={setEditingExpense} onDelete={setDeletingExpense} />
      )}

      {editingExpense && (
        <Modal title={t('expenses.editTitle')} onClose={() => setEditingExpense(null)}>
          <ExpenseForm
            defaultValues={expenseToFormValues(editingExpense)}
            submitLabel={t('expenses.saveChanges')}
            isSubmitting={updateMutation.isPending}
            submitError={updateMutation.isError ? toApiError(updateMutation.error).message : null}
            onSubmit={(values) => updateMutation.mutate(values)}
          />
        </Modal>
      )}

      {deletingExpense && (
        <Modal title={t('expenses.deleteTitle')} onClose={() => setDeletingExpense(null)}>
          <p className="text-sm text-slate-600">
            <Trans
              i18nKey="expenses.deleteConfirm"
              values={{ name: deletingExpense.business_name }}
              components={{ bold: <strong /> }}
            />
          </p>
          {deleteMutation.isError && (
            <p role="alert" className="mt-2 text-sm text-danger-600">
              {toApiError(deleteMutation.error).message}
            </p>
          )}
          <div className="mt-4 flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setDeletingExpense(null)}
              className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              {t('common.cancel')}
            </button>
            <button
              type="button"
              disabled={deleteMutation.isPending}
              onClick={() => {
                if (deleteMutation.isPending) return
                deleteMutation.mutate(deletingExpense.id)
              }}
              className="rounded-md bg-danger-600 px-4 py-2 text-sm font-semibold text-white hover:bg-danger-700 disabled:opacity-60"
            >
              {deleteMutation.isPending ? t('common.deleting') : t('common.delete')}
            </button>
          </div>
        </Modal>
      )}
    </div>
  )
}
