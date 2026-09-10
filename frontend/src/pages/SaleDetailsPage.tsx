import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'

import { DocumentStatusBadge } from '../components/DocumentStatusBadge'
import { FormField, inputClasses } from '../components/FormField'
import { Modal } from '../components/Modal'
import { ReceiptImage } from '../components/ReceiptImage'
import { SaleForm } from '../components/SaleForm'
import { SaleStatusBadge } from '../components/SaleStatusBadge'
import { ErrorState, LoadingState } from '../components/StatusStates'
import { formatCurrency, formatDateTime } from '../lib/format'
import { toApiError } from '../services/apiClient'
import { getSale, getSaleEvents, refundSale, updateSale } from '../services/saleService'
import type { SaleFormInput, SaleFormValues } from '../schemas/sale'
import type { PaymentMethod, TransactionCurrency } from '../types/sale'
import type { SaleEventType } from '../types/saleEvent'

function normalizePaymentMethod(value: string | null): PaymentMethod | '' {
  const known = ['card', 'cash', 'other']
  if (!value) return ''
  return (known.includes(value) ? value : 'other') as PaymentMethod | ''
}

function normalizeCurrency(value: string): TransactionCurrency {
  return (['ILS', 'USD', 'EUR'].includes(value) ? value : 'ILS') as TransactionCurrency
}

function Field({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs font-medium text-stone-500 dark:text-stone-400">{label}</dt>
      <dd className="mt-0.5 truncate text-sm font-medium text-stone-900 dark:text-stone-100">{value}</dd>
      {hint && <p className="mt-0.5 text-xs text-stone-400 dark:text-stone-500">{hint}</p>}
    </div>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm dark:border-stone-800 dark:bg-stone-900">
      <h2 className="text-sm font-semibold text-stone-900 dark:text-stone-100">{title}</h2>
      <dl className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">{children}</dl>
    </div>
  )
}

const EVENT_TONE: Record<SaleEventType, string> = {
  sale_received: 'bg-brand-500',
  sale_created_manually: 'bg-brand-500',
  sale_imported_from_csv: 'bg-brand-500',
  payment_succeeded: 'bg-success-500',
  payment_pending: 'bg-accent-500',
  payment_failed: 'bg-danger-500',
  document_issuance_attempted: 'bg-stone-400',
  document_issued: 'bg-success-500',
  document_issuance_failed: 'bg-danger-500',
  refund_partial: 'bg-amber-500',
  refund_full: 'bg-amber-500',
  sale_details_edited: 'bg-stone-400',
}

export function SaleDetailsPage() {
  const { id } = useParams<{ id: string }>()
  const { t, i18n } = useTranslation()
  const queryClient = useQueryClient()
  const [isEditOpen, setIsEditOpen] = useState(false)
  const [refundInput, setRefundInput] = useState('')
  const [isRefundOpen, setIsRefundOpen] = useState(false)
  const [isDocumentOpen, setIsDocumentOpen] = useState(false)

  const saleQuery = useQuery({ queryKey: ['sale', id], queryFn: () => getSale(id as string), enabled: !!id })
  const eventsQuery = useQuery({
    queryKey: ['sale-events', id],
    queryFn: () => getSaleEvents(id as string),
    enabled: !!id,
  })

  const updateMutation = useMutation({
    mutationFn: (values: SaleFormValues) =>
      updateSale(id as string, {
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
      queryClient.invalidateQueries({ queryKey: ['sale', id] })
      queryClient.invalidateQueries({ queryKey: ['sale-events', id] })
      queryClient.invalidateQueries({ queryKey: ['sales'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] })
      setIsEditOpen(false)
    },
  })

  const refundMutation = useMutation({
    mutationFn: (amount?: number) => refundSale(id as string, amount),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sale', id] })
      queryClient.invalidateQueries({ queryKey: ['sale-events', id] })
      queryClient.invalidateQueries({ queryKey: ['sales'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] })
      setIsRefundOpen(false)
      setRefundInput('')
    },
  })

  if (saleQuery.isLoading) return <LoadingState label={t('common.loading')} />
  if (saleQuery.isError) {
    return <ErrorState message={toApiError(saleQuery.error).message} onRetry={() => saleQuery.refetch()} />
  }
  const sale = saleQuery.data
  if (!sale) return null

  const grossAmount = Number(sale.gross_amount)
  const vatAmount = sale.vat_amount != null ? Number(sale.vat_amount) : null
  const revenueBeforeVat = vatAmount != null ? grossAmount - vatAmount : null
  const netAmount = Number(sale.net_amount)
  const refundedAmount = sale.refunded_amount != null ? Number(sale.refunded_amount) : 0
  // Mirrors Sale.revenue_contribution() on the backend (see app/models/sale.py) —
  // a read-only presentation value, never itself a source of financial truth.
  const remainingAfterRefunds =
    sale.status === 'pending' || sale.status === 'failed' || sale.status === 'refunded'
      ? 0
      : Math.max(netAmount - refundedAmount, 0)
  const refundableRemaining = Math.max(netAmount - refundedAmount, 0)

  const editDefaults: Partial<SaleFormInput> = {
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

  return (
    <div className="max-w-4xl space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <Link to="/sales" className="text-sm font-medium text-brand-600 hover:text-brand-700 dark:text-brand-400">
            {t('saleDetails.backToSales')}
          </Link>
          <h1 className="mt-1 text-2xl font-semibold text-stone-900 dark:text-stone-100">{sale.customer_name}</h1>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <SaleStatusBadge status={sale.status} />
            <DocumentStatusBadge status={sale.document_status} />
            <span className="text-xs text-stone-400 dark:text-stone-500">{t(`saleSource.${sale.source}`)}</span>
          </div>
        </div>
        <div className="flex gap-2">
          {(sale.status === 'succeeded' || sale.status === 'partially_refunded') && refundableRemaining > 0 && (
            <button
              type="button"
              onClick={() => setIsRefundOpen(true)}
              className="rounded-md border border-stone-300 bg-white px-4 py-2 text-sm font-semibold text-stone-700 hover:bg-stone-50 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-200 dark:hover:bg-stone-700"
            >
              {t('saleDetails.recordRefund')}
            </button>
          )}
          <button
            type="button"
            onClick={() => setIsEditOpen(true)}
            className="rounded-md bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700"
          >
            {t('saleDetails.editSale')}
          </button>
        </div>
      </div>

      <Section title={t('saleDetails.customerAndService')}>
        <Field label={t('form.customerName')} value={sale.customer_name} />
        <Field label={t('form.customerContact')} value={sale.customer_contact || t('saleDetails.notProvided')} />
        <Field label={t('form.serviceName')} value={sale.service_name} />
        <Field label={t('saleDetails.description')} value={sale.description || t('saleDetails.notProvided')} />
      </Section>

      <Section title={t('saleDetails.originAndTiming')}>
        <Field label={t('saleDetails.source')} value={t(`saleSource.${sale.source}`)} />
        <Field label={t('saleDetails.sourceProvider')} value={sale.source_provider || t('saleDetails.notApplicable')} />
        <Field label={t('saleDetails.externalReference')} value={sale.external_id || t('saleDetails.notApplicable')} />
        <Field label={t('saleDetails.occurredAt')} value={formatDateTime(sale.occurred_at, i18n.language)} />
      </Section>

      <Section title={t('saleDetails.paymentAndCurrency')}>
        <Field label={t('saleDetails.status')} value={<SaleStatusBadge status={sale.status} />} />
        <Field
          label={t('form.paymentMethod')}
          value={sale.payment_method ? t(`paymentMethod.${sale.payment_method}`, sale.payment_method) : t('saleDetails.notProvided')}
        />
        <Field label={t('form.currency')} value={t(`currency.${sale.currency}`, sale.currency)} />
      </Section>

      <Section title={t('saleDetails.financialBreakdown')}>
        <Field
          label={t('saleDetails.grossAmount')}
          value={formatCurrency(sale.gross_amount, sale.currency, i18n.language)}
          hint={t('saleDetails.grossAmountHint')}
        />
        <Field
          label={t('form.taxTreatment')}
          value={
            sale.tax_treatment ? (
              t(`taxTreatment.${sale.tax_treatment}`)
            ) : (
              <span className="inline-flex items-center rounded-full bg-amber-500/10 px-2 py-0.5 text-xs font-semibold text-amber-700 dark:text-amber-400">
                {t('sales.taxTreatmentNeedsReview')}
              </span>
            )
          }
        />
        <Field
          label={t('saleDetails.vatRate')}
          value={sale.vat_rate != null ? `${(Number(sale.vat_rate) * 100).toFixed(0)}%` : t('saleDetails.notApplicable')}
        />
        <Field
          label={t('form.vatAmount')}
          value={vatAmount != null ? formatCurrency(vatAmount, sale.currency, i18n.language) : t('saleDetails.notApplicable')}
          hint={t('saleDetails.vatAmountHint')}
        />
        <Field
          label={t('saleDetails.revenueBeforeVat')}
          value={revenueBeforeVat != null ? formatCurrency(revenueBeforeVat, sale.currency, i18n.language) : t('saleDetails.notApplicable')}
          hint={t('saleDetails.revenueBeforeVatHint')}
        />
        <Field
          label={t('form.processingFee')}
          value={sale.processing_fee != null ? formatCurrency(sale.processing_fee, sale.currency, i18n.language) : t('saleDetails.notApplicable')}
          hint={t('saleDetails.processingFeeHint')}
        />
        <Field
          label={t('saleDetails.netRevenue')}
          value={formatCurrency(sale.net_amount, sale.currency, i18n.language)}
          hint={t('saleDetails.netRevenueHint')}
        />
        <Field
          label={t('saleDetails.refundedAmount')}
          value={sale.refunded_amount != null ? formatCurrency(sale.refunded_amount, sale.currency, i18n.language) : formatCurrency(0, sale.currency, i18n.language)}
        />
        <Field
          label={t('saleDetails.remainingAfterRefunds')}
          value={formatCurrency(remainingAfterRefunds, sale.currency, i18n.language)}
          hint={t('saleDetails.remainingAfterRefundsHint')}
        />
      </Section>

      <Section title={t('saleDetails.customerDocument')}>
        <Field label={t('saleDetails.documentStatus')} value={<DocumentStatusBadge status={sale.document_status} />} />
        <Field label={t('saleDetails.documentNumber')} value={sale.document_number || t('saleDetails.notApplicable')} />
        {sale.document_url && (
          <div className="sm:col-span-2">
            <button
              type="button"
              onClick={() => setIsDocumentOpen(true)}
              className="rounded-md border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 hover:bg-stone-50 dark:border-stone-700 dark:text-stone-200 dark:hover:bg-stone-800"
            >
              {t('sales.viewDocument')}
            </button>
          </div>
        )}
      </Section>

      <div className="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm dark:border-stone-800 dark:bg-stone-900">
        <h2 className="text-sm font-semibold text-stone-900 dark:text-stone-100">{t('saleDetails.timeline')}</h2>
        {eventsQuery.isLoading && <LoadingState label={t('common.loading')} />}
        {eventsQuery.isError && <ErrorState message={toApiError(eventsQuery.error).message} />}
        {eventsQuery.data && eventsQuery.data.length === 0 && (
          <p className="mt-3 text-sm text-stone-500 dark:text-stone-400">{t('saleDetails.noHistoryAvailable')}</p>
        )}
        {eventsQuery.data && eventsQuery.data.length > 0 && (
          <ol className="mt-4 space-y-3">
            {eventsQuery.data.map((event) => (
              <li key={event.id} className="flex items-start gap-3">
                <span
                  className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${EVENT_TONE[event.event_type] ?? 'bg-stone-400'}`}
                  aria-hidden="true"
                />
                <div className="min-w-0">
                  <p className="text-sm font-medium text-stone-900 dark:text-stone-100">
                    {t(`saleEvent.${event.event_type}`)}
                  </p>
                  <p className="text-xs text-stone-400 dark:text-stone-500">
                    {formatDateTime(event.created_at, i18n.language)} · {t(`saleEventSource.${event.source}`)}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        )}
        <p className="mt-4 text-xs text-stone-400 dark:text-stone-500">{t('saleDetails.timelineHonestyNote')}</p>
      </div>

      {isEditOpen && (
        <Modal title={t('saleDetails.editSale')} onClose={() => setIsEditOpen(false)}>
          <SaleForm
            defaultValues={editDefaults}
            submitLabel={t('sales.saveChanges')}
            isSubmitting={updateMutation.isPending}
            submitError={updateMutation.isError ? toApiError(updateMutation.error).message : null}
            taxTreatmentNeedsReview={sale.tax_treatment_needs_review}
            onSubmit={(values) => updateMutation.mutate(values)}
          />
        </Modal>
      )}

      {isRefundOpen && (
        <Modal title={t('saleDetails.recordRefund')} onClose={() => setIsRefundOpen(false)}>
          <p className="text-sm text-stone-600 dark:text-stone-400">
            {t('saleDetails.refundableAmount', { amount: formatCurrency(refundableRemaining, sale.currency, i18n.language) })}
          </p>
          <FormField label={t('saleDetails.refundAmountLabel')} htmlFor="refund_amount" hint={t('saleDetails.refundAmountHint')}>
            <input
              id="refund_amount"
              type="number"
              step="0.01"
              min="0.01"
              max={refundableRemaining}
              placeholder={t('saleDetails.refundFullPlaceholder')}
              className={inputClasses}
              value={refundInput}
              onChange={(event) => setRefundInput(event.target.value)}
            />
          </FormField>
          {refundMutation.isError && (
            <p role="alert" className="mt-2 text-sm text-danger-600">
              {toApiError(refundMutation.error).message}
            </p>
          )}
          <div className="mt-4 flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setIsRefundOpen(false)}
              className="rounded-md border border-stone-300 px-4 py-2 text-sm font-medium text-stone-700 hover:bg-stone-50 dark:border-stone-700 dark:text-stone-200 dark:hover:bg-stone-800"
            >
              {t('common.cancel')}
            </button>
            <button
              type="button"
              disabled={refundMutation.isPending}
              onClick={() => refundMutation.mutate(refundInput ? Number(refundInput) : undefined)}
              className="rounded-md bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
            >
              {refundMutation.isPending ? t('common.saving') : t('saleDetails.confirmRefund')}
            </button>
          </div>
        </Modal>
      )}

      {isDocumentOpen && sale.document_url && (
        <Modal title={t('sales.viewDocumentTitle', { name: sale.customer_name })} onClose={() => setIsDocumentOpen(false)}>
          <ReceiptImage url={sale.document_url} alt={t('sales.documentImageAlt', { name: sale.customer_name })} />
        </Modal>
      )}
    </div>
  )
}
