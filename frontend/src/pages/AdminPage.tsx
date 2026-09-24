import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Building2, Plus, Search, ShieldCheck, Trash2, X } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Navigate } from 'react-router-dom'

import { ConfirmDialog } from '../components/ConfirmDialog'
import { FormField, inputClasses } from '../components/FormField'
import { Modal } from '../components/Modal'
import { EmptyState, ErrorState, LoadingState } from '../components/StatusStates'
import { Card, PageHeader } from '../components/ui'
import { buttonClasses } from '../components/ui-classes'
import { useAuth } from '../contexts/AuthContext'
import { formatDate } from '../lib/format'
import { addBusinessProvider, deleteBusinessAsAdmin, listAdminBusinesses, removeBusinessProvider, type AdminBusiness } from '../services/adminService'
import type { PaymentProvider } from '../services/businessService'

const PROVIDER_LABELS: Record<PaymentProvider, string> = { grow: 'Grow', cardcom: 'Cardcom' }

export function AdminPage() {
  const { t, i18n } = useTranslation()
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [deleteTarget, setDeleteTarget] = useState<AdminBusiness | null>(null)
  const [providerRemovalTarget, setProviderRemovalTarget] = useState<{ business: AdminBusiness; provider: PaymentProvider } | null>(null)
  const [confirmName, setConfirmName] = useState('')
  const { data = [], isPending: isLoading, isError, refetch } = useQuery({ queryKey: ['admin-businesses'], queryFn: listAdminBusinesses })
  const addProvider = useMutation({
    mutationFn: ({ businessId, provider }: { businessId: string; provider: PaymentProvider }) => addBusinessProvider(businessId, provider),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin-businesses'] }),
  })
  const removeProvider = useMutation({
    mutationFn: ({ businessId, provider }: { businessId: string; provider: PaymentProvider }) => removeBusinessProvider(businessId, provider),
    onSuccess: () => {
      setProviderRemovalTarget(null)
      queryClient.invalidateQueries({ queryKey: ['admin-businesses'] })
    },
  })
  const removeBusiness = useMutation({
    mutationFn: ({ businessId, name }: { businessId: string; name: string }) => deleteBusinessAsAdmin(businessId, name),
    onSuccess: () => {
      setDeleteTarget(null); setConfirmName('')
      queryClient.invalidateQueries({ queryKey: ['admin-businesses'] })
    },
  })
  const filtered = useMemo(() => {
    const term = search.trim().toLocaleLowerCase()
    if (!term) return data
    return data.filter((business) => [business.name, business.business_number, ...business.owner_emails]
      .some((value) => value?.toLocaleLowerCase().includes(term)))
  }, [data, search])

  if (user?.system_role !== 'admin') return <Navigate to="/app" replace />

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={<span className="inline-flex items-center gap-1.5"><ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />{t('admin.eyebrow')}</span>}
        title={t('admin.title')}
        description={t('admin.subtitle')}
        actions={
          <div className="relative w-full sm:w-80">
            <Search className="pointer-events-none absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" aria-hidden="true" />
            <input
              type="search"
              aria-label={t('admin.searchLabel')}
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={t('admin.searchPlaceholder')}
              className={`${inputClasses} ps-9`}
            />
          </div>
        }
      />
      {isLoading && <LoadingState label={t('admin.loading')} />}
      {isError && <ErrorState message={t('admin.loadError')} onRetry={() => refetch()} />}
      {!isLoading && !isError && filtered.length === 0 && <EmptyState title={t('admin.noResults')} icon={<Building2 className="h-5 w-5" />} />}
      <div className="grid gap-4 xl:grid-cols-2">
        {filtered.map((business) => (
          <Card as="article" key={business.id} className="flex flex-col">
            <div className="flex flex-wrap items-start justify-between gap-3 p-5">
              <div className="flex min-w-0 items-start gap-3">
                <span className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-brand-50 text-brand-700 ring-1 ring-brand-100 dark:bg-brand-500/10 dark:text-brand-300 dark:ring-brand-500/20" aria-hidden="true">
                  <Building2 className="h-5 w-5" />
                </span>
                <div className="min-w-0">
                  <h2 className="font-semibold break-words text-zinc-900 dark:text-zinc-50">{business.name}</h2>
                  <p className="mt-1 truncate text-xs text-zinc-600 dark:text-zinc-400" dir="ltr">{business.owner_emails.join(', ') || t('admin.ownersUnavailable')}</p>
                  <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
                    {business.business_number ? t('admin.businessNumber', { number: business.business_number }) : t('admin.noBusinessNumber')}
                    {' · '}
                    {t('admin.createdAt', { date: formatDate(business.created_at.slice(0, 10), i18n.language) })}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => { setDeleteTarget(business); setConfirmName('') }}
                aria-label={t('admin.deleteBusinessFor', { name: business.name })}
                className={buttonClasses('ghost', 'sm', 'text-danger-700 hover:bg-danger-50 hover:text-danger-700 dark:text-danger-500 dark:hover:bg-danger-500/10')}
              >
                <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                {t('admin.deleteBusiness')}
              </button>
            </div>
            <dl className="mx-5 grid grid-cols-3 divide-x divide-zinc-200 rounded-lg bg-zinc-50 py-3 text-center dark:divide-zinc-800 dark:bg-zinc-950/40">
              {([['sales', business.sale_count], ['connections', business.connection_count], ['members', business.member_count]] as const).map(([key, value]) => (
                <div key={key}>
                  <dd className="figure text-lg font-medium text-zinc-900 dark:text-zinc-50">{value}</dd>
                  <dt className="text-xs text-zinc-500 dark:text-zinc-400">{t(`admin.stats.${key}`)}</dt>
                </div>
              ))}
            </dl>
            <div className="mt-auto flex flex-wrap items-center gap-2 p-5">
              <span className="me-1 text-sm font-medium text-zinc-700 dark:text-zinc-300">{t('admin.providers')}</span>
              {(['grow', 'cardcom'] as PaymentProvider[]).map((provider) => business.payment_providers.includes(provider)
                ? (
                  <span key={provider} className="inline-flex items-center gap-1 rounded-full bg-success-50 py-0.5 ps-3 pe-0.5 text-xs font-medium text-success-700 ring-1 ring-success-500/20 ring-inset dark:bg-success-500/10 dark:text-success-500">
                    <span>{PROVIDER_LABELS[provider]}</span>
                    <button
                      type="button"
                      aria-label={t('admin.removeProviderFor', { provider: PROVIDER_LABELS[provider], business: business.name })}
                      onClick={() => setProviderRemovalTarget({ business, provider })}
                      className="grid h-6 w-6 place-items-center rounded-full hover:bg-danger-50 hover:text-danger-700 dark:hover:bg-danger-500/15"
                    >
                      <X className="h-3.5 w-3.5" aria-hidden="true" />
                    </button>
                  </span>
                )
                : (
                  <button
                    key={provider}
                    type="button"
                    disabled={addProvider.isPending}
                    onClick={() => addProvider.mutate({ businessId: business.id, provider })}
                    className="inline-flex h-7 items-center gap-1 rounded-full border border-dashed border-zinc-300 px-3 text-xs font-medium text-zinc-600 transition-colors hover:border-brand-500 hover:text-brand-700 disabled:opacity-50 dark:border-zinc-600 dark:text-zinc-300 dark:hover:border-brand-400 dark:hover:text-brand-300"
                  >
                    <Plus className="h-3 w-3" aria-hidden="true" />
                    {t('admin.addProvider', { provider: PROVIDER_LABELS[provider] })}
                  </button>
                ))}
            </div>
          </Card>
        ))}
      </div>

      {providerRemovalTarget && (
        <ConfirmDialog
          title={t('admin.removeProviderTitle', { provider: PROVIDER_LABELS[providerRemovalTarget.provider] })}
          description={t('admin.removeProviderDescription', { business: providerRemovalTarget.business.name })}
          confirmLabel={t('admin.removeProviderConfirm')}
          isLoading={removeProvider.isPending}
          error={removeProvider.isError ? t('admin.removeProviderError') : null}
          onClose={() => setProviderRemovalTarget(null)}
          onConfirm={() => removeProvider.mutate({ businessId: providerRemovalTarget.business.id, provider: providerRemovalTarget.provider })}
        />
      )}

      {deleteTarget && (
        <Modal title={t('admin.deleteTitle', { name: deleteTarget.name })} onClose={() => setDeleteTarget(null)}>
          <p className="text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">{t('admin.deleteDescription')}</p>
          <div className="mt-5">
            <FormField label={t('admin.deleteConfirmLabel')} htmlFor="confirm-business-name">
              <input id="confirm-business-name" autoFocus value={confirmName} onChange={(event) => setConfirmName(event.target.value)} className={inputClasses} autoComplete="off" />
            </FormField>
          </div>
          {removeBusiness.isError && (
            <p role="alert" className="mt-3 rounded-lg bg-danger-50 px-3 py-2 text-sm text-danger-700 dark:bg-danger-500/10 dark:text-danger-500">{t('admin.deleteError')}</p>
          )}
          <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <button type="button" onClick={() => setDeleteTarget(null)} className={buttonClasses('secondary')}>{t('common.cancel')}</button>
            <button
              type="button"
              disabled={confirmName !== deleteTarget.name || removeBusiness.isPending}
              onClick={() => removeBusiness.mutate({ businessId: deleteTarget.id, name: confirmName })}
              className={buttonClasses('danger')}
            >
              {removeBusiness.isPending ? t('admin.deleting') : t('admin.deleteConfirm')}
            </button>
          </div>
        </Modal>
      )}
    </div>
  )
}
