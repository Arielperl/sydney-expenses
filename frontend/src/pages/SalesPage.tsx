import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Trans, useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { SaleForm } from '../components/SaleForm'
import { SaleList } from '../components/SaleList'
import { Modal } from '../components/Modal'
import { ReceiptImage } from '../components/ReceiptImage'
import { EmptyState, ErrorState, LoadingState } from '../components/StatusStates'
import { inputClasses } from '../components/FormField'
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
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState<SaleStatus | ''>('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [editingSale, setEditingSale] = useState<Sale | null>(null)
  const [deletingSale, setDeletingSale] = useState<Sale | null>(null)
  const [viewingDocumentSale, setViewingDocumentSale] = useState<Sale | null>(null)

  const queryClient = useQueryClient()
  const filters = { search, status, date_from: dateFrom, date_to: dateTo }

  const { data, isLoading, isError, error, refetch } = useQuery({
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
      setEditingSale(null)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteSale(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sales'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] })
      setDeletingSale(null)
    },
  })

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-stone-900 dark:text-stone-100">{t('sales.title')}</h1>
          <p className="mt-1 text-sm text-stone-500 dark:text-stone-400">{t('sales.subtitle')}</p>
        </div>
        <Link
          to="/add-sale"
          className="shrink-0 rounded-md border border-stone-300 bg-white px-4 py-2 text-sm font-semibold text-stone-700 hover:bg-stone-50 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-200 dark:hover:bg-stone-700"
        >
          {t('sales.addSaleManually')}
        </Link>
      </div>

      <div className="flex flex-col gap-3 rounded-2xl border border-stone-200 bg-white p-4 shadow-sm sm:flex-row sm:flex-wrap dark:border-stone-800 dark:bg-stone-900">
        <div className="min-w-0 sm:flex-[2_2_240px]">
          <label htmlFor="search" className="sr-only">
            {t('sales.searchLabel')}
          </label>
          <input
            id="search"
            className={inputClasses}
            placeholder={t('sales.searchPlaceholder')}
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
        <div className="min-w-0 sm:flex-1 sm:basis-40">
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
        <div className="flex min-w-0 gap-2 sm:flex-1 sm:basis-56">
          <input
            aria-label={t('sales.dateFromLabel')}
            type="date"
            className={`${inputClasses} min-w-0 flex-1`}
            value={dateFrom}
            onChange={(event) => setDateFrom(event.target.value)}
          />
          <input
            aria-label={t('sales.dateToLabel')}
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
        <EmptyState title={t('sales.emptyTitle')} description={t('sales.emptyDescription')} />
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
          <p className="text-sm text-stone-600 dark:text-stone-400">
            <Trans
              i18nKey="sales.deleteConfirm"
              values={{ name: deletingSale.customer_name }}
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
              onClick={() => setDeletingSale(null)}
              className="rounded-md border border-stone-300 px-4 py-2 text-sm font-medium text-stone-700 hover:bg-stone-50 dark:border-stone-700 dark:text-stone-200 dark:hover:bg-stone-800"
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
