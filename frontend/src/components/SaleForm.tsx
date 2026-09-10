import { zodResolver } from '@hookform/resolvers/zod'
import type { ReactNode } from 'react'
import { useForm } from 'react-hook-form'
import type { TFunction } from 'i18next'
import { useTranslation } from 'react-i18next'

import { FormField, inputClasses } from './FormField'
import { saleFormSchema, type SaleFormInput, type SaleFormValues } from '../schemas/sale'
import { todayIsoDate } from '../lib/format'
import { PAYMENT_METHODS } from '../types/sale'

const DEFAULT_VALUES: SaleFormInput = {
  customer_name: '',
  customer_contact: '',
  service_name: '',
  gross_amount: 0,
  vat_amount: '',
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
}: {
  defaultValues?: Partial<SaleFormInput>
  onSubmit: (values: SaleFormValues) => void | Promise<void>
  submitLabel?: string
  isSubmitting?: boolean
  submitError?: string | null
  extraContent?: ReactNode
}) {
  const { t } = useTranslation()
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<SaleFormInput, unknown, SaleFormValues>({
    resolver: zodResolver(saleFormSchema),
    defaultValues: { ...DEFAULT_VALUES, ...defaultValues },
  })

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
          label={t('form.vatAmount')}
          htmlFor="vat_amount"
          error={translateError(t, errors.vat_amount?.message as string | undefined)}
        >
          <input
            id="vat_amount"
            type="number"
            step="0.01"
            min="0"
            className={inputClasses}
            {...register('vat_amount')}
          />
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
          <input id="currency" className={inputClasses} maxLength={3} {...register('currency')} />
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
