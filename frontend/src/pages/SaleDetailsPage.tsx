import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { ChevronRight, ExternalLink, FileText, FileUp, Pencil, Undo2 } from 'lucide-react'
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
import { Money } from '../components/Money'
import { Badge, Card } from '../components/ui'
import { buttonClasses, cx } from '../components/ui-classes'
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

function Field({ label, value, hint, wide }: { label: string; value: ReactNode; hint?: string; wide?: boolean }) {
  return (
    <div className={cx('min-w-0', wide && 'sm:col-span-2')}>
      <dt className="text-xs text-zinc-500 dark:text-zinc-400">{label}</dt>
      <dd className="mt-1 text-sm font-medium break-words text-zinc-900 dark:text-zinc-100">{value}</dd>
      {hint && <p className="mt-0.5 text-xs text-zinc-500 dark:text-zinc-400">{hint}</p>}
    </div>
  )
}

function Section({ title, children, columns = 2 }: { title: string; children: ReactNode; columns?: 1 | 2 }) {
  return (
    <Card>
      <h2 className="border-b border-zinc-100 px-5 py-3.5 text-sm font-semibold text-zinc-900 dark:border-zinc-800 dark:text-zinc-50">{title}</h2>
      <dl className={cx('grid grid-cols-1 gap-x-6 gap-y-4 p-5', columns === 2 && 'sm:grid-cols-2')}>{children}</dl>
    </Card>
  )
}

/** One line of the per-sale money statement: label + definition on one side, amount on the other. */
function StatementRow({ label, hint, value, emphasis, muted }: { label: string; hint?: string; value: ReactNode; emphasis?: boolean; muted?: boolean }) {
  return (
    <div className={cx('flex items-start justify-between gap-4 px-5 py-3', emphasis && 'bg-brand-50/60 dark:bg-brand-500/5')}>
      <dt className="min-w-0">
        <span className={cx('text-sm', emphasis ? 'font-semibold text-zinc-900 dark:text-zinc-50' : 'text-zinc-700 dark:text-zinc-300')}>{label}</span>
        {hint && <p className="mt-0.5 max-w-sm text-xs leading-relaxed text-zinc-500 dark:text-zinc-400">{hint}</p>}
      </dt>
      <dd className={cx('shrink-0 text-end text-sm whitespace-nowrap', emphasis ? 'font-semibold text-zinc-900 dark:text-zinc-50' : 'font-medium', muted ? 'text-zinc-500 dark:text-zinc-400' : 'text-zinc-900 dark:text-zinc-100')}>
        {value}
      </dd>
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
  document_issuance_attempted: 'bg-zinc-400',
  document_issued: 'bg-success-500',
  document_issuance_failed: 'bg-danger-500',
  refund_partial: 'bg-amber-500',
  refund_full: 'bg-amber-500',
  sale_details_edited: 'bg-zinc-400',
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
      queryClient.invalidateQueries({ queryKey: ['exception-center'] })
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
      queryClient.invalidateQueries({ queryKey: ['exception-center'] })
      setIsRefundOpen(false)
      setRefundInput('')
    },
  })

  if (saleQuery.isPending) return <LoadingState label={t('common.loading')} />
  if (saleQuery.isError) {
    return <ErrorState message={toApiError(saleQuery.error).message} onRetry={() => saleQuery.refetch()} />
  }
  const sale = saleQuery.data
  if (!sale) return null

  // Grow's invoice URL is an external page on Grow's own domain (never
  // fetched by us — see backend grow_provider.py) — a plain external link,
  // never rendered as an <img>. Every other document_url (manual/mock
  // attachment) is our own stored image, previewed inline via the modal
  // below. Cardcom never sets document_url at all (its DocumentUrl is
  // documented as unreliable), so it never reaches either branch.
  const isExternalProviderDocument = Boolean(sale.source_provider?.startsWith('grow:'))

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

  const notApplicable = <span className="font-normal text-zinc-500 dark:text-zinc-400">{t('saleDetails.notApplicable')}</span>
  const money = (value: number | string) => <Money amount={value} currency={sale.currency} />

  return (
    <div className="space-y-6">
      <div>
        <Link to="/sales" className="inline-flex items-center gap-1 text-sm font-medium text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100">
          <ChevronRight className="h-4 w-4 ltr:rotate-180" aria-hidden="true" />
          {t('saleDetails.backToSales')}
        </Link>
        <div className="mt-3 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div className="min-w-0">
            <h1 className="text-[1.625rem] leading-tight font-semibold tracking-[-0.015em] break-words text-zinc-900 dark:text-zinc-50">{sale.customer_name}</h1>
            <div className="mt-2.5 flex flex-wrap items-center gap-2">
              <SaleStatusBadge status={sale.status} />
              <DocumentStatusBadge status={sale.document_status} />
              <span className="text-xs text-zinc-500 dark:text-zinc-400">
                {sale.service_name} · {t(`saleSource.${sale.source}`)} · <bdi>{formatDateTime(sale.occurred_at, i18n.language)}</bdi>
              </span>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {(sale.status === 'succeeded' || sale.status === 'partially_refunded') && refundableRemaining > 0 && (
              <button type="button" onClick={() => setIsRefundOpen(true)} className={buttonClasses('secondary')}>
                <Undo2 className="h-4 w-4" aria-hidden="true" />
                {t('saleDetails.recordRefund')}
              </button>
            )}
            <button type="button" onClick={() => setIsEditOpen(true)} className={buttonClasses('primary')}>
              <Pencil className="h-4 w-4" aria-hidden="true" />
              {t('saleDetails.editSale')}
            </button>
          </div>
        </div>
      </div>

      {/* The three numbers people open a sale for, before the full statement below. */}
      <Card as="div">
        <dl aria-label={t('saleDetails.keyFigures')} className="grid grid-cols-1 divide-y divide-zinc-100 sm:grid-cols-3 sm:divide-x sm:divide-y-0 dark:divide-zinc-800">
          {[
            { key: 'gross', label: t('saleDetails.grossAmount'), value: money(sale.gross_amount) },
            { key: 'vat', label: t('form.vatAmount'), value: vatAmount != null ? money(vatAmount) : notApplicable },
            { key: 'remaining', label: t('saleDetails.remainingAfterRefunds'), value: money(remainingAfterRefunds) },
          ].map((figure) => (
            <div key={figure.key} className="min-w-0 px-5 py-4 sm:px-6">
              <dt className="text-sm text-zinc-600 dark:text-zinc-400">{figure.label}</dt>
              <dd className="mt-1.5 text-lg font-medium text-zinc-900 dark:text-zinc-50">{figure.value}</dd>
            </div>
          ))}
        </dl>
      </Card>

      <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,22rem)]">
        <div className="space-y-6">
          <Card>
            <h2 className="border-b border-zinc-100 px-5 py-3.5 text-sm font-semibold text-zinc-900 dark:border-zinc-800 dark:text-zinc-50">{t('saleDetails.financialBreakdown')}</h2>
            <dl className="divide-y divide-zinc-100 dark:divide-zinc-800">
              <StatementRow label={t('saleDetails.grossAmount')} hint={t('saleDetails.grossAmountHint')} value={money(sale.gross_amount)} />
              <StatementRow
                label={t('form.taxTreatment')}
                value={sale.tax_treatment ? t(`taxTreatment.${sale.tax_treatment}`) : <Badge tone="warning">{t('sales.taxTreatmentNeedsReview')}</Badge>}
              />
              <StatementRow label={t('saleDetails.vatRate')} value={sale.vat_rate != null ? <bdi className="figure">{`${(Number(sale.vat_rate) * 100).toFixed(0)}%`}</bdi> : notApplicable} />
              <StatementRow label={t('form.vatAmount')} hint={t('saleDetails.vatAmountHint')} value={vatAmount != null ? money(vatAmount) : notApplicable} />
              <StatementRow label={t('saleDetails.revenueBeforeVat')} hint={t('saleDetails.revenueBeforeVatHint')} value={revenueBeforeVat != null ? money(revenueBeforeVat) : notApplicable} />
              <StatementRow label={t('form.processingFee')} hint={t('saleDetails.processingFeeHint')} value={sale.processing_fee != null ? money(sale.processing_fee) : notApplicable} />
              <StatementRow label={t('saleDetails.netRevenue')} hint={t('saleDetails.netRevenueHint')} value={money(sale.net_amount)} />
              <StatementRow label={t('saleDetails.refundedAmount')} value={money(sale.refunded_amount != null ? sale.refunded_amount : 0)} muted={refundedAmount === 0} />
              <StatementRow label={t('saleDetails.remainingAfterRefunds')} hint={t('saleDetails.remainingAfterRefundsHint')} value={money(remainingAfterRefunds)} emphasis />
            </dl>
          </Card>

          <Section title={t('saleDetails.customerAndService')}>
            <Field label={t('form.customerName')} value={sale.customer_name} />
            <Field label={t('form.customerContact')} value={sale.customer_contact ? <bdi>{sale.customer_contact}</bdi> : t('saleDetails.notProvided')} />
            <Field label={t('form.serviceName')} value={sale.service_name} />
            <Field label={t('saleDetails.description')} value={sale.description || t('saleDetails.notProvided')} wide={Boolean(sale.description && sale.description.length > 60)} />
          </Section>

          <Card>
            <h2 className="border-b border-zinc-100 px-5 py-3.5 text-sm font-semibold text-zinc-900 dark:border-zinc-800 dark:text-zinc-50">{t('saleDetails.timeline')}</h2>
            <div className="p-5">
              {eventsQuery.isPending && <LoadingState label={t('common.loading')} />}
              {eventsQuery.isError && <ErrorState message={toApiError(eventsQuery.error).message} />}
              {eventsQuery.data && eventsQuery.data.length === 0 && (
                <p className="text-sm text-zinc-500 dark:text-zinc-400">{t('saleDetails.noHistoryAvailable')}</p>
              )}
              {eventsQuery.data && eventsQuery.data.length > 0 && (
                <ol className="relative space-y-4 before:absolute before:inset-y-1.5 before:start-[3px] before:w-px before:bg-zinc-200 dark:before:bg-zinc-800">
                  {eventsQuery.data.map((event) => (
                    <li key={event.id} className="relative flex items-start gap-3.5">
                      <span
                        className={`relative mt-1.5 h-[7px] w-[7px] shrink-0 rounded-full ring-4 ring-white dark:ring-zinc-900 ${EVENT_TONE[event.event_type] ?? 'bg-zinc-400'}`}
                        aria-hidden="true"
                      />
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
                          {t(`saleEvent.${event.event_type}`)}
                        </p>
                        <p className="mt-0.5 text-xs text-zinc-500 dark:text-zinc-400">
                          <bdi>{formatDateTime(event.created_at, i18n.language)}</bdi> · {t(`saleEventSource.${event.source}`)}
                        </p>
                      </div>
                    </li>
                  ))}
                </ol>
              )}
              <p className="mt-5 text-xs leading-relaxed text-zinc-500 dark:text-zinc-400">{t('saleDetails.timelineHonestyNote')}</p>
            </div>
          </Card>
        </div>

        <div className="space-y-6">
          <Section title={t('saleDetails.customerDocument')} columns={1}>
            <Field label={t('saleDetails.documentStatus')} value={<DocumentStatusBadge status={sale.document_status} />} />
            <Field label={t('saleDetails.documentNumber')} value={sale.document_number || t('saleDetails.notApplicable')} />
            <Field label={t('saleDetails.documentType')} value={sale.document_type || t('saleDetails.notApplicable')} />
            {sale.document_status === 'waiting_automatic' && (
              <p className="rounded-lg bg-sky-50 px-3 py-2 text-xs leading-relaxed text-sky-900 dark:bg-sky-500/10 dark:text-sky-200">
                {t('saleDetails.documentWaitingAutomaticHint')}
              </p>
            )}
            {(sale.document_url || (sale.document_status !== 'issued' && sale.document_status !== 'not_required')) && (
              <div className="flex flex-wrap items-center gap-2">
                {sale.document_url && isExternalProviderDocument ? (
                  <a href={sale.document_url} target="_blank" rel="noopener noreferrer" className={buttonClasses('secondary', 'sm')}>
                    <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
                    {t('sales.viewDocument')}
                  </a>
                ) : (
                  sale.document_url && (
                    <button type="button" onClick={() => setIsDocumentOpen(true)} className={buttonClasses('secondary', 'sm')}>
                      <FileText className="h-3.5 w-3.5" aria-hidden="true" />
                      {t('sales.viewDocument')}
                    </button>
                  )
                )}
                {sale.document_status !== 'issued' && sale.document_status !== 'not_required' && (
                  <Link to={`/import-document?saleId=${sale.id}`} className={buttonClasses('subtle', 'sm')}>
                    <FileUp className="h-3.5 w-3.5" aria-hidden="true" />
                    {t('saleDetails.attachDocumentManually')}
                  </Link>
                )}
              </div>
            )}
          </Section>

          <Section title={t('saleDetails.paymentAndCurrency')} columns={1}>
            <Field label={t('saleDetails.status')} value={<SaleStatusBadge status={sale.status} />} />
            <Field
              label={t('form.paymentMethod')}
              value={sale.payment_method ? t(`paymentMethod.${sale.payment_method}`, sale.payment_method) : t('saleDetails.notProvided')}
            />
            <Field label={t('form.currency')} value={t(`currency.${sale.currency}`, sale.currency)} />
          </Section>

          <Section title={t('saleDetails.originAndTiming')} columns={1}>
            <Field label={t('saleDetails.source')} value={t(`saleSource.${sale.source}`)} />
            <Field label={t('saleDetails.sourceProvider')} value={sale.source_provider ? <bdi>{sale.source_provider}</bdi> : t('saleDetails.notApplicable')} />
            <Field label={t('saleDetails.externalReference')} value={sale.external_id ? <bdi className="font-mono text-xs">{sale.external_id}</bdi> : t('saleDetails.notApplicable')} />
            <Field label={t('saleDetails.occurredAt')} value={<bdi>{formatDateTime(sale.occurred_at, i18n.language)}</bdi>} />
          </Section>
        </div>
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
          <p className="mb-4 rounded-lg bg-zinc-50 px-3 py-2.5 text-sm text-zinc-700 dark:bg-zinc-800/60 dark:text-zinc-300">
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
            <p role="alert" className="mt-3 rounded-lg bg-danger-50 px-3 py-2 text-sm text-danger-700 dark:bg-danger-500/10 dark:text-danger-500">
              {toApiError(refundMutation.error).message}
            </p>
          )}
          <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <button
              type="button"
              onClick={() => setIsRefundOpen(false)}
              className={buttonClasses('secondary')}
            >
              {t('common.cancel')}
            </button>
            <button
              type="button"
              disabled={refundMutation.isPending}
              onClick={() => refundMutation.mutate(refundInput ? Number(refundInput) : undefined)}
              className={buttonClasses('primary')}
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
