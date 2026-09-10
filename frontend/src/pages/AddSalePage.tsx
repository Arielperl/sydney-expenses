import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import { SaleForm } from '../components/SaleForm'
import { createSale } from '../services/saleService'
import { toApiError } from '../services/apiClient'
import type { SaleFormValues } from '../schemas/sale'

export function AddSalePage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [showSuccess, setShowSuccess] = useState(false)

  const mutation = useMutation({
    mutationFn: (values: SaleFormValues) =>
      createSale({
        customer_name: values.customer_name,
        customer_contact: values.customer_contact || null,
        service_name: values.service_name,
        gross_amount: Number(values.gross_amount),
        tax_treatment: values.tax_treatment,
        processing_fee: values.processing_fee === '' ? null : Number(values.processing_fee),
        currency: values.currency,
        occurred_at: values.sale_date,
        payment_method: values.payment_method || null,
        description: values.description || null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sales'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] })
      setShowSuccess(true)
      setTimeout(() => navigate('/sales'), 900)
    },
  })

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-stone-900 dark:text-stone-100">{t('addSale.title')}</h1>
        <p className="mt-1 text-sm text-stone-500 dark:text-stone-400">{t('addSale.subtitle')}</p>
      </div>

      {showSuccess && (
        <div
          role="status"
          className="rounded-lg border border-success-500/30 bg-success-50 p-3 text-sm text-success-700 dark:bg-success-500/10 dark:text-success-400"
        >
          {t('addSale.successMessage')}
        </div>
      )}

      <div className="rounded-2xl border border-stone-200 bg-white p-6 shadow-sm dark:border-stone-800 dark:bg-stone-900">
        <SaleForm
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
