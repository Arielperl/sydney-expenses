import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Building2, Minus, Plus, Search } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { ConfirmDialog } from '../../components/ConfirmDialog'
import { inputClasses } from '../../components/FormField'
import { EmptyState, ErrorState, LoadingState } from '../../components/StatusStates'
import { Card } from '../../components/ui'
import { buttonClasses, cx } from '../../components/ui-classes'
import { addBusinessProvider, listAdminBusinesses, removeBusinessProvider } from '../../services/adminService'
import type { PaymentProvider } from '../../services/businessService'

const PROVIDERS: { value: PaymentProvider; label: string }[] = [
  { value: 'grow', label: 'Grow' },
  { value: 'cardcom', label: 'Cardcom' },
]

export function BusinessesPanel() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [removal, setRemoval] = useState<{ businessId: string; businessName: string; provider: PaymentProvider } | null>(null)
  const businesses = useQuery({ queryKey: ['staff-businesses'], queryFn: listAdminBusinesses })
  const refresh = () => void queryClient.invalidateQueries({ queryKey: ['staff-businesses'] })
  const addProvider = useMutation({
    mutationFn: ({ businessId, provider }: { businessId: string; provider: PaymentProvider }) => addBusinessProvider(businessId, provider),
    onSuccess: refresh,
  })
  const removeProvider = useMutation({
    mutationFn: ({ businessId, provider }: { businessId: string; provider: PaymentProvider }) => removeBusinessProvider(businessId, provider),
    onSuccess: () => { setRemoval(null); refresh() },
  })
  const query = search.trim().toLocaleLowerCase()
  const shown = businesses.data?.filter((item) => [item.name, ...item.owner_emails].some((value) => value.toLocaleLowerCase().includes(query))) ?? []

  return (
    <section aria-labelledby="businesses-heading" className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <h2 id="businesses-heading" className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">{t('supportPortal.businesses.title')}</h2>
          <p className="mt-0.5 text-sm text-zinc-500 dark:text-zinc-400">{t('supportPortal.businesses.description')}</p>
        </div>
        <div className="relative w-full sm:w-80">
          <Search className="pointer-events-none absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-400" aria-hidden="true" />
          <label htmlFor="support-business-search" className="sr-only">{t('supportPortal.businesses.searchLabel')}</label>
          <input
            id="support-business-search"
            type="search"
            className={cx(inputClasses, 'ps-9')}
            placeholder={t('supportPortal.businesses.searchPlaceholder')}
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
      </div>

      {businesses.isPending && <LoadingState label={t('supportPortal.businesses.loading')} />}
      {businesses.isError && <ErrorState message={t('supportPortal.businesses.loadError')} onRetry={() => void businesses.refetch()} />}
      {businesses.data && shown.length === 0 && <EmptyState title={t('supportPortal.businesses.empty')} icon={<Building2 className="h-5 w-5" />} />}

      <div className="grid gap-4 md:grid-cols-2">
        {shown.map((business) => (
          <Card key={business.id} as="article" className="flex flex-col p-5">
            <div className="flex items-start gap-3">
              <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-brand-50 text-brand-700 ring-1 ring-brand-100 dark:bg-brand-500/10 dark:text-brand-300 dark:ring-brand-500/20" aria-hidden="true">
                <Building2 className="h-4 w-4" />
              </span>
              <div className="min-w-0">
                <h3 className="truncate font-semibold text-zinc-900 dark:text-zinc-50" title={business.name}>{business.name}</h3>
                <p className="mt-0.5 truncate text-sm text-zinc-500 dark:text-zinc-400" dir="ltr" title={business.owner_emails.join(', ')}>
                  {business.owner_emails.join(', ')}
                </p>
                <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
                  {t('supportPortal.businesses.sales', { count: business.sale_count })} · {t('supportPortal.businesses.connections', { count: business.connection_count })}
                </p>
              </div>
            </div>
            <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-zinc-100 pt-4 dark:border-zinc-800">
              <span className="me-1 text-xs font-medium text-zinc-500 dark:text-zinc-400">{t('supportPortal.businesses.providers')}</span>
              {PROVIDERS.map(({ value, label }) =>
                business.payment_providers.includes(value) ? (
                  <button
                    key={value}
                    type="button"
                    className={buttonClasses('secondary', 'sm')}
                    onClick={() => setRemoval({ businessId: business.id, businessName: business.name, provider: value })}
                  >
                    <Minus className="h-3.5 w-3.5" aria-hidden="true" />
                    {t('supportPortal.businesses.remove', { provider: label })}
                  </button>
                ) : (
                  <button
                    key={value}
                    type="button"
                    disabled={addProvider.isPending}
                    className={buttonClasses('subtle', 'sm')}
                    onClick={() => addProvider.mutate({ businessId: business.id, provider: value })}
                  >
                    <Plus className="h-3.5 w-3.5" aria-hidden="true" />
                    {t('supportPortal.businesses.add', { provider: label })}
                  </button>
                ),
              )}
            </div>
          </Card>
        ))}
      </div>
      {(addProvider.isError || removeProvider.isError) && (
        <p role="alert" className="text-sm text-danger-700 dark:text-danger-500">{t('supportPortal.businesses.actionError')}</p>
      )}

      {removal && (
        <ConfirmDialog
          title={t('supportPortal.businesses.removeTitle', { provider: removal.provider === 'grow' ? 'Grow' : 'Cardcom' })}
          description={t('supportPortal.businesses.removeDescription', { business: removal.businessName })}
          confirmLabel={t('supportPortal.businesses.removeConfirm')}
          isLoading={removeProvider.isPending}
          error={removeProvider.isError ? t('supportPortal.businesses.removeError') : null}
          onClose={() => setRemoval(null)}
          onConfirm={() => removeProvider.mutate({ businessId: removal.businessId, provider: removal.provider })}
        />
      )}
    </section>
  )
}
