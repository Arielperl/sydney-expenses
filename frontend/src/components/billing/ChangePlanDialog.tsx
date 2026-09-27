import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Info } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { catalogSavingsMonths, planByCode } from '../../lib/billing'
import { BILLING_QUERY_KEY, changePlan, type BillingInterval, type BillingOverview } from '../../services/billingService'
import { Modal } from '../Modal'
import { buttonClasses } from '../ui-classes'
import { IntervalToggle, PlanCards } from './PlanCards'

export function ChangePlanDialog({ overview, onClose }: { overview: BillingOverview; onClose: () => void }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const sub = overview.subscription
  const [interval, setInterval] = useState<BillingInterval>(sub?.billing_interval ?? 'month')
  const [planCode, setPlanCode] = useState<string | null>(null)
  const chosen = planByCode(overview.plans, planCode)
  const unchanged = !sub || (planCode === sub.plan_code && interval === sub.billing_interval && !sub.pending_plan_code)
  const paid = sub?.status === 'active' || sub?.status === 'past_due'
  const mutation = useMutation({
    mutationFn: () => changePlan(planCode as string, interval),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: BILLING_QUERY_KEY })
      onClose()
    },
  })

  return (
    <Modal title={t('billing.changePlan.title')} onClose={mutation.isPending ? () => {} : onClose} size="xl">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <p className="flex max-w-xl items-start gap-2 text-sm leading-relaxed text-zinc-600 dark:text-zinc-300">
          <Info className="mt-0.5 h-4 w-4 shrink-0 text-zinc-400" aria-hidden="true" />
          {paid ? t('billing.changePlan.paidNote') : t('billing.changePlan.trialNote')}
        </p>
        <IntervalToggle surface="app" value={interval} onChange={setInterval} savingsMonths={catalogSavingsMonths(overview.plans)} />
      </div>
      <form
        className="mt-6"
        onSubmit={(event) => {
          event.preventDefault()
          if (planCode && !unchanged) mutation.mutate()
        }}
      >
        <PlanCards
          plans={overview.plans}
          interval={interval}
          surface="app"
          currentPlanCode={sub?.plan_code}
          selection={{ name: 'change-plan', value: planCode, onChange: setPlanCode, label: t('billing.changePlan.select') }}
        />
        {mutation.isError && (
          <p role="alert" className="mt-5 rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700 dark:bg-danger-500/10 dark:text-red-200">
            {mutation.error.message || t('billing.changePlan.error')}
          </p>
        )}
        <div className="sticky bottom-0 -mx-5 mt-6 flex flex-col-reverse gap-2 border-t border-zinc-100 bg-white px-5 pt-4 sm:-mx-6 sm:flex-row sm:justify-end sm:px-6 dark:border-zinc-800 dark:bg-zinc-900">
          <button type="button" className={buttonClasses('ghost')} onClick={onClose} disabled={mutation.isPending}>
            {t('billing.changePlan.cancel')}
          </button>
          <button type="submit" className={buttonClasses('primary')} disabled={!planCode || unchanged || mutation.isPending}>
            {mutation.isPending
              ? t('billing.changePlan.saving')
              : chosen ? t('billing.changePlan.confirm', { plan: chosen.name }) : t('billing.changePlan.select')}
          </button>
        </div>
      </form>
    </Modal>
  )
}
