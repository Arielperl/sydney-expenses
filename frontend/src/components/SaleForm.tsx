import { zodResolver } from '@hookform/resolvers/zod'
import type { ReactNode } from 'react'
import { useForm, useWatch } from 'react-hook-form'
import type { TFunction } from 'i18next'
import { useTranslation } from 'react-i18next'

import { FormField, inputClasses } from './FormField'
import { saleFormSchema, type SaleFormInput, type SaleFormValues } from '../schemas/sale'
import { formatCurrency, todayIsoDate } from '../lib/format'
import { previewVat } from '../lib/vat'
import { PAYMENT_METHODS, TAX_TREATMENTS, TRANSACTION_CURRENCIES } from '../types/sale'

const DEFAULT_VALUES: SaleFormInput = {
  customer_name: '',
  customer_contact: '',
  service_name: '',
  gross_amount: 0,
  tax_treatment: 'standard',
  processing_fee: '',
  currency: 'ILS',
  sale_date: todayIsoDate(),
  payment_method: '',
  description: '',
}

function translateError(t: TFunction, message: string | undefined): string | undefined {
  return message ? t(message) : undefined
}

export function SaleForm({
  defaultValues,
  onSubmit,
  submitLabel,
  isSubmitting = false,
  submitError,
  extraContent,
  taxTreatmentNeedsReview = false,
}: {
  defaultValues?: Partial<SaleFormInput>
  onSubmit: (values: SaleFormValues) => void | Promise<void>
  submitLabel?: string
  isSubmitting?: boolean
  submitError?: string | null
  extraContent?: ReactNode
  /** True when this edit targets a legacy sale whose tax treatment a data
   * migration couldn't safely infer (see the backend migration) — the form
   * still defaults its tax-treatment select to something concrete (never
   * leaves it blank), but shows a note that this is the first time it's
   * being set rather than pretending it was always "standard". */
  taxTreatmentNeedsReview?: boolean
}) {
  const { t, i18n } = useTranslation()
  const {
    register,
    handleSubmit,
    control,
    formState: { errors },
  } = useForm<SaleFormInput, unknown, SaleFormValues>({
    resolver: zodResolver(saleFormSchema),
    defaultValues: { ...DEFAULT_VALUES, ...defaultValues },
  })

  const grossAmount = useWatch({ control, name: 'gross_amount' })
  const taxTreatment = useWatch({ control, name: 'tax_treatment' })
  const currency = useWatch({ control, name: 'currency' })
  const numericGross = grossAmount === '' || grossAmount === undefined ? 0 : Number(grossAmount)
  const vatPreview = previewVat(numericGross, (taxTreatment || 'standard') as SaleFormInput['tax_treatment'] & string)

  function guardedSubmit(values: SaleFormValues) {
    if (isSubmitting) return
    return onSubmit(values)
  }

  return (
    <form onSubmit={handleSubmit(guardedSubmit)} noValidate className="space-y-5">
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
        <FormField
          label={t('form.customerName')}
          htmlFor="customer_name"
          required
          error={translateError(t, errors.customer_name?.message)}
        >
          <input
            id="customer_name"
            className={inputClasses}
            placeholder={t('form.customerNamePlaceholder')}
            {...register('customer_name')}
          />
        </FormField>

        <FormField
          label={t('form.customerContact')}
          htmlFor="customer_contact"
          hint={t('form.customerContactHint')}
          error={translateError(t, errors.customer_contact?.message)}
        >
          <input
            id="customer_contact"
            className={inputClasses}
            placeholder={t('form.customerContactPlaceholder')}
            {...register('customer_contact')}
          />
        </FormField>

        <FormField
          label={t('form.serviceName')}
          htmlFor="service_name"
          required
          error={translateError(t, errors.service_name?.message)}
        >
          <input
            id="service_name"
            className={inputClasses}
            placeholder={t('form.serviceNamePlaceholder')}
            {...register('service_name')}
          />
        </FormField>

        <FormField
          label={t('form.grossAmount')}
          htmlFor="gross_amount"
          required
          error={translateError(t, errors.gross_amount?.message)}
        >
          <input
            id="gross_amount"
            type="number"
            step="0.01"
            min="0"
            className={inputClasses}
            {...register('gross_amount')}
          />
        </FormField>

        <FormField
          label={t('form.taxTreatment')}
          htmlFor="tax_treatment"
          required
          hint={taxTreatmentNeedsReview ? t('form.taxTreatmentNeedsReviewHint') : undefined}
          error={translateError(t, errors.tax_treatment?.message)}
        >
          <select id="tax_treatment" className={inputClasses} {...register('tax_treatment')}>
            {TAX_TREATMENTS.map((treatment) => (
              <option key={treatment} value={treatment}>
                {t(`taxTreatment.${treatment}`)}
              </option>
            ))}
          </select>
        </FormField>

        <FormField label={t('form.vatAmount')} htmlFor="vat_amount_preview">
          <p
            id="vat_amount_preview"
            className="flex h-10 items-center rounded-md border border-dashed border-zinc-300 bg-zinc-50 px-3 text-sm text-zinc-600 dark:border-zinc-700 dark:bg-zinc-800/50 dark:text-zinc-400"
          >
            {formatCurrency(vatPreview, currency || 'ILS', i18n.language)}
            <span className="ms-2 text-xs text-zinc-400 dark:text-zinc-500">{t('form.vatAmountPreviewHint')}</span>
          </p>
        </FormField>

        <FormField
          label={t('form.processingFee')}
          htmlFor="processing_fee"
          error={translateError(t, errors.processing_fee?.message as string | undefined)}
        >
          <input
            id="processing_fee"
            type="number"
            step="0.01"
            min="0"
            className={inputClasses}
            {...register('processing_fee')}
          />
        </FormField>

        <FormField
          label={t('form.currency')}
          htmlFor="currency"
          required
          error={translateError(t, errors.currency?.message)}
        >
          <select id="currency" className={inputClasses} {...register('currency')}>
            {TRANSACTION_CURRENCIES.map((code) => (
              <option key={code} value={code}>
                {t(`currency.${code}`)}
              </option>
            ))}
          </select>
        </FormField>

        <FormField
          label={t('form.saleDate')}
          htmlFor="sale_date"
          required
          error={translateError(t, errors.sale_date?.message)}
        >
          <input id="sale_date" type="date" className={inputClasses} {...register('sale_date')} />
        </FormField>

        <FormField
          label={t('form.paymentMethod')}
          htmlFor="payment_method"
          error={translateError(t, errors.payment_method?.message)}
        >
          <select id="payment_method" className={inputClasses} {...register('payment_method')}>
            <option value="">{t('form.paymentMethodPlaceholder')}</option>
            {PAYMENT_METHODS.map((method) => (
              <option key={method} value={method}>
                {t(`paymentMethod.${method}`)}
              </option>
            ))}
          </select>
        </FormField>
      </div>

      <FormField label={t('form.description')} htmlFor="description" error={translateError(t, errors.description?.message)}>
        <textarea id="description" rows={3} className={inputClasses} {...register('description')} />
      </FormField>

      {extraContent}

      {submitError && (
        <p role="alert" className="text-sm text-danger-600">
          {submitError}
        </p>
      )}

      <button
        type="submit"
        disabled={isSubmitting}
        className="inline-flex items-center rounded-md bg-brand-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-brand-700 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {isSubmitting ? t('common.saving') : (submitLabel ?? t('form.saveSale'))}
      </button>
    </form>
  )
}
