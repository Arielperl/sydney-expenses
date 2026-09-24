import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ChevronRight, CircleCheck } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'

import { SaleForm } from '../components/SaleForm'
import { PageHeader } from '../components/ui'
import { cardClasses, cx } from '../components/ui-classes'
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
      queryClient.invalidateQueries({ queryKey: ['exception-center'] })
      setShowSuccess(true)
      setTimeout(() => navigate('/sales'), 900)
    },
  })

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <Link to="/sales" className="mb-3 inline-flex items-center gap-1 text-sm font-medium text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100">
          <ChevronRight className="h-4 w-4 ltr:rotate-180" aria-hidden="true" />
          {t('nav.sales')}
        </Link>
        <PageHeader title={t('addSale.title')} description={t('addSale.subtitle')} />
      </div>

      {showSuccess && (
        <div
          role="status"
          className="flex animate-pop-in items-center gap-2 rounded-lg border border-success-500/25 bg-success-50 px-4 py-3 text-sm font-medium text-success-700 dark:bg-success-500/10 dark:text-success-500"
        >
          <CircleCheck className="h-4 w-4 shrink-0" aria-hidden="true" />
          {t('addSale.successMessage')}
        </div>
      )}

      <div className={cx(cardClasses, 'p-5 sm:p-6')}>
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
