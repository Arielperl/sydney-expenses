import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { PlugZap, Plus, Search, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Trans, useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'

import { SaleForm } from '../components/SaleForm'
import { SaleList } from '../components/SaleList'
import { Modal } from '../components/Modal'
import { ReceiptImage } from '../components/ReceiptImage'
import { EmptyState, ErrorState, LoadingState } from '../components/StatusStates'
import { inputClasses } from '../components/FormField'
import { PageHeader } from '../components/ui'
import { buttonClasses } from '../components/ui-classes'
import { deleteSale, listSales, updateSale } from '../services/saleService'
import { toApiError } from '../services/apiClient'
import type { SaleFormInput, SaleFormValues } from '../schemas/sale'
import type { Sale, SaleStatus } from '../types/sale'
import { PAYMENT_METHODS, SALE_STATUSES, TRANSACTION_CURRENCIES } from '../types/sale'

// A sale's stored payment_method isn't guaranteed to be one of the values the
// <select> offers — webhook ingestion accepts a payment provider's own method
// names as-is, and older records may predate this closed set entirely. This
// is the one place that normalizes any such legacy/unknown value down to
// "other" so the edit form always has a valid option selected, never a blank
// or crashing select.
function normalizePaymentMethod(value: string | null): (typeof PAYMENT_METHODS)[number] | '' {
  if (!value) return ''
  return (PAYMENT_METHODS as readonly string[]).includes(value)
    ? (value as (typeof PAYMENT_METHODS)[number])
    : 'other'
}

// A sale's stored currency isn't guaranteed to be one of the three the
// <select> offers — CSV/webhook ingestion isn't restricted to this closed
// set (see backend app/schemas/validators.py). Same normalization pattern
// as payment_method above: an unrecognized legacy/ingested value falls back
// to the business's own default (ILS) in the edit form only, never mutating
// the stored sale.
function normalizeCurrency(value: string): (typeof TRANSACTION_CURRENCIES)[number] {
  return (TRANSACTION_CURRENCIES as readonly string[]).includes(value)
    ? (value as (typeof TRANSACTION_CURRENCIES)[number])
    : 'ILS'
}

function saleToFormValues(sale: Sale): SaleFormInput {
  return {
    customer_name: sale.customer_name,
    customer_contact: sale.customer_contact ?? '',
    service_name: sale.service_name,
    gross_amount: sale.gross_amount,
    tax_treatment: sale.tax_treatment ?? 'standard',
    processing_fee: sale.processing_fee ?? '',
    currency: normalizeCurrency(sale.currency),
    sale_date: sale.occurred_at.slice(0, 10),
    payment_method: normalizePaymentMethod(sale.payment_method),
    description: sale.description ?? '',
  }
}

export function SalesPage() {
  const { t } = useTranslation()
  // Read initial filters from the URL (e.g. a dashboard "needs attention"
  // link to `/sales?status=failed`) so a deep link actually filters the
  // page, not just navigates to it — then keep the URL in sync as the user
  // changes filters, so the current view stays shareable/refreshable.
  const [searchParams, setSearchParams] = useSearchParams()
  const [search, setSearch] = useState(searchParams.get('search') ?? '')
  const [status, setStatus] = useState<SaleStatus | ''>((searchParams.get('status') as SaleStatus | null) ?? '')
  const [dateFrom, setDateFrom] = useState(searchParams.get('date_from') ?? '')
  const [dateTo, setDateTo] = useState(searchParams.get('date_to') ?? '')
  const [editingSale, setEditingSale] = useState<Sale | null>(null)
  const [deletingSale, setDeletingSale] = useState<Sale | null>(null)
  const [viewingDocumentSale, setViewingDocumentSale] = useState<Sale | null>(null)

  const queryClient = useQueryClient()
  const filters = { search, status, date_from: dateFrom, date_to: dateTo }

  useEffect(() => {
    const next = new URLSearchParams()
    if (search) next.set('search', search)
    if (status) next.set('status', status)
    if (dateFrom) next.set('date_from', dateFrom)
    if (dateTo) next.set('date_to', dateTo)
    setSearchParams(next, { replace: true })
  }, [search, status, dateFrom, dateTo, setSearchParams])

  const { data, isPending: isLoading, isError, error, refetch } = useQuery({
    queryKey: ['sales', filters],
    queryFn: () => listSales(filters),
  })

  const updateMutation = useMutation({
    mutationFn: (values: SaleFormValues) => {
      if (!editingSale) throw new Error('No sale selected')
      return updateSale(editingSale.id, {
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
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sales'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] })
      queryClient.invalidateQueries({ queryKey: ['exception-center'] })
      setEditingSale(null)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteSale(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sales'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] })
      queryClient.invalidateQueries({ queryKey: ['exception-center'] })
      setDeletingSale(null)
    },
  })

  const hasFilters = Boolean(search || status || dateFrom || dateTo)

  function clearFilters() {
    setSearch('')
    setStatus('')
    setDateFrom('')
    setDateTo('')
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={t('sales.title')}
        description={t('sales.subtitle')}
        actions={
          <>
            <Link to="/imports" className={buttonClasses('secondary')}>
              <PlugZap className="h-4 w-4" aria-hidden="true" />
              {t('nav.imports')}
            </Link>
            <Link to="/add-sale" className={buttonClasses('primary')}>
              <Plus className="h-4 w-4" aria-hidden="true" />
              {t('sales.addSaleManually')}
            </Link>
          </>
        }
      />

      <div className="space-y-3">
        <div className="flex flex-col gap-2.5 sm:flex-row sm:flex-wrap sm:items-center">
          <div className="relative min-w-0 sm:flex-[2_2_260px]">
            <label htmlFor="search" className="sr-only">
              {t('sales.searchLabel')}
            </label>
            <Search className="pointer-events-none absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" aria-hidden="true" />
            <input
              id="search"
              type="search"
              className={`${inputClasses} ps-9`}
              placeholder={t('sales.searchPlaceholder')}
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>
          <div className="min-w-0 sm:flex-1 sm:basis-44">
            <label htmlFor="status-filter" className="sr-only">
              {t('sales.statusFilterLabel')}
            </label>
            <select
              id="status-filter"
              className={inputClasses}
              value={status}
              onChange={(event) => setStatus(event.target.value as SaleStatus | '')}
            >
              <option value="">{t('sales.allStatuses')}</option>
              {SALE_STATUSES.map((item) => (
                <option key={item} value={item}>
                  {t(`saleStatus.${item}`)}
                </option>
              ))}
            </select>
          </div>
          <div className="flex min-w-0 items-center gap-2 sm:flex-1 sm:basis-64">
            <input
              aria-label={t('sales.dateFromLabel')}
              type="date"
              className={`${inputClasses} min-w-0 flex-1`}
              value={dateFrom}
              onChange={(event) => setDateFrom(event.target.value)}
            />
            <span className="text-zinc-500" aria-hidden="true">–</span>
            <input
              aria-label={t('sales.dateToLabel')}
              type="date"
              className={`${inputClasses} min-w-0 flex-1`}
              value={dateTo}
              onChange={(event) => setDateTo(event.target.value)}
            />
          </div>
        </div>
        {!isLoading && !isError && data && (
          <div className="flex min-h-8 flex-wrap items-center justify-between gap-2 text-sm text-zinc-500 dark:text-zinc-400">
            <p aria-live="polite">{t('sales.resultCount', { count: data.length })}</p>
            {hasFilters && (
              <button type="button" onClick={clearFilters} className={buttonClasses('ghost', 'sm')}>
                <X className="h-3.5 w-3.5" aria-hidden="true" />
                {t('sales.clearFilters')}
              </button>
            )}
          </div>
        )}
      </div>

      {isLoading && <LoadingState />}
      {isError && <ErrorState message={toApiError(error).message} onRetry={() => refetch()} />}
      {!isLoading && !isError && data && data.length === 0 && (
        <EmptyState
          title={t('sales.emptyTitle')}
          description={t('sales.emptyDescription')}
          action={hasFilters
            ? <button type="button" onClick={clearFilters} className={buttonClasses('secondary')}>{t('sales.clearFilters')}</button>
            : <Link to="/add-sale" className={buttonClasses('primary')}>{t('sales.addSaleManually')}</Link>}
        />
      )}
      {!isLoading && !isError && data && data.length > 0 && (
        <SaleList
          sales={data}
          onEdit={setEditingSale}
          onDelete={setDeletingSale}
          onViewDocument={setViewingDocumentSale}
        />
      )}

      {viewingDocumentSale && viewingDocumentSale.document_url && (
        <Modal
          title={t('sales.viewDocumentTitle', { name: viewingDocumentSale.customer_name })}
          onClose={() => setViewingDocumentSale(null)}
        >
          <ReceiptImage
            url={viewingDocumentSale.document_url}
            alt={t('sales.documentImageAlt', { name: viewingDocumentSale.customer_name })}
          />
        </Modal>
      )}

      {editingSale && (
        <Modal title={t('sales.editTitle')} onClose={() => setEditingSale(null)}>
          <SaleForm
            defaultValues={saleToFormValues(editingSale)}
            submitLabel={t('sales.saveChanges')}
            isSubmitting={updateMutation.isPending}
            submitError={updateMutation.isError ? toApiError(updateMutation.error).message : null}
            taxTreatmentNeedsReview={editingSale.tax_treatment_needs_review}
            onSubmit={(values) => updateMutation.mutate(values)}
          />
        </Modal>
      )}

      {deletingSale && (
        <Modal title={t('sales.deleteTitle')} onClose={() => setDeletingSale(null)}>
          <p className="text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">
            <Trans
              i18nKey="sales.deleteConfirm"
              values={{ name: deletingSale.customer_name }}
              components={{ bold: <strong /> }}
            />
          </p>
          {deleteMutation.isError && (
            <p role="alert" className="mt-3 rounded-lg bg-danger-50 px-3 py-2 text-sm text-danger-700 dark:bg-danger-500/10 dark:text-danger-500">
              {toApiError(deleteMutation.error).message}
            </p>
          )}
          <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <button
              type="button"
              onClick={() => setDeletingSale(null)}
              className={buttonClasses('secondary')}
            >
              {t('common.cancel')}
            </button>
            <button
              type="button"
              disabled={deleteMutation.isPending}
              onClick={() => {
                if (deleteMutation.isPending) return
                deleteMutation.mutate(deletingSale.id)
              }}
              className={buttonClasses('danger')}
            >
              {deleteMutation.isPending ? t('common.deleting') : t('common.delete')}
            </button>
          </div>
        </Modal>
      )}
    </div>
  )
}
