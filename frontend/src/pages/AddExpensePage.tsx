import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import { ExpenseForm } from '../components/ExpenseForm'
import { createExpense } from '../services/expenseService'
import { toApiError } from '../services/apiClient'
import type { ExpenseFormValues } from '../schemas/expense'

export function AddExpensePage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [showSuccess, setShowSuccess] = useState(false)

  const mutation = useMutation({
    mutationFn: (values: ExpenseFormValues) =>
      createExpense({
        ...values,
        receipt_number: values.receipt_number || null,
        vat_amount: values.vat_amount === '' ? null : Number(values.vat_amount),
        payment_method: values.payment_method || null,
        notes: values.notes || null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['expenses'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] })
      setShowSuccess(true)
      setTimeout(() => navigate('/expenses'), 900)
    },
  })

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">{t('addExpense.title')}</h1>
        <p className="mt-1 text-sm text-slate-500">{t('addExpense.subtitle')}</p>
      </div>

      {showSuccess && (
        <div
          role="status"
          className="rounded-lg border border-success-500/30 bg-success-50 p-3 text-sm text-success-700"
        >
          {t('addExpense.successMessage')}
        </div>
      )}

      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <ExpenseForm
          onSubmit={(values) => {
            if (mutation.isPending) return
            mutation.mutate(values)
          }}
          isSubmitting={mutation.isPending}
          submitError={mutation.isError ? toApiError(mutation.error).message : null}
        />
      </div>
    </div>
  )
}
