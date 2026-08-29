import { zodResolver } from '@hookform/resolvers/zod'
import type { ReactNode } from 'react'
import { useForm } from 'react-hook-form'
import type { TFunction } from 'i18next'
import { useTranslation } from 'react-i18next'

import { FormField, inputClasses } from './FormField'
import { expenseFormSchema, type ExpenseFormInput, type ExpenseFormValues } from '../schemas/expense'
import { EXPENSE_CATEGORIES } from '../types/expense'
import { todayIsoDate } from '../lib/format'

const DEFAULT_VALUES: ExpenseFormInput = {
  business_name: '',
  receipt_number: '',
  amount: 0,
  vat_amount: '',
  currency: 'ILS',
  category: 'other',
  expense_date: todayIsoDate(),
  payment_method: '',
  notes: '',
}

function translateError(t: TFunction, message: string | undefined): string | undefined {
  return message ? t(message) : undefined
}

export function ExpenseForm({
  defaultValues,
  onSubmit,
  submitLabel,
  isSubmitting = false,
  submitError,
  extraContent,
}: {
  defaultValues?: Partial<ExpenseFormInput>
  onSubmit: (values: ExpenseFormValues) => void | Promise<void>
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
  } = useForm<ExpenseFormInput, unknown, ExpenseFormValues>({
    resolver: zodResolver(expenseFormSchema),
    defaultValues: { ...DEFAULT_VALUES, ...defaultValues },
  })

  function guardedSubmit(values: ExpenseFormValues) {
    if (isSubmitting) return
    return onSubmit(values)
  }

  return (
    <form onSubmit={handleSubmit(guardedSubmit)} noValidate className="space-y-5">
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
        <FormField
          label={t('form.businessName')}
          htmlFor="business_name"
          required
          error={translateError(t, errors.business_name?.message)}
        >
          <input
            id="business_name"
            className={inputClasses}
            placeholder={t('form.businessNamePlaceholder')}
            {...register('business_name')}
          />
        </FormField>

        <FormField
          label={t('form.receiptNumber')}
          htmlFor="receipt_number"
          error={translateError(t, errors.receipt_number?.message)}
        >
          <input id="receipt_number" className={inputClasses} {...register('receipt_number')} />
        </FormField>

        <FormField
          label={t('form.amount')}
          htmlFor="amount"
          required
          error={translateError(t, errors.amount?.message)}
        >
          <input
            id="amount"
            type="number"
            step="0.01"
            min="0"
            className={inputClasses}
            {...register('amount')}
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
          label={t('form.currency')}
          htmlFor="currency"
          required
          error={translateError(t, errors.currency?.message)}
        >
          <input id="currency" className={inputClasses} maxLength={3} {...register('currency')} />
        </FormField>

        <FormField
          label={t('form.category')}
          htmlFor="category"
          required
          error={translateError(t, errors.category?.message)}
        >
          <select id="category" className={inputClasses} {...register('category')}>
            {EXPENSE_CATEGORIES.map((category) => (
              <option key={category} value={category}>
                {t(`categories.${category}`)}
              </option>
            ))}
          </select>
        </FormField>

        <FormField
          label={t('form.expenseDate')}
          htmlFor="expense_date"
          required
          error={translateError(t, errors.expense_date?.message)}
        >
          <input id="expense_date" type="date" className={inputClasses} {...register('expense_date')} />
        </FormField>

        <FormField
          label={t('form.paymentMethod')}
          htmlFor="payment_method"
          error={translateError(t, errors.payment_method?.message)}
        >
          <input
            id="payment_method"
            className={inputClasses}
            placeholder={t('form.paymentMethodPlaceholder')}
            {...register('payment_method')}
          />
        </FormField>
      </div>

      <FormField label={t('form.notes')} htmlFor="notes" error={translateError(t, errors.notes?.message)}>
        <textarea id="notes" rows={3} className={inputClasses} {...register('notes')} />
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
        {isSubmitting ? t('common.saving') : (submitLabel ?? t('form.saveExpense'))}
      </button>
    </form>
  )
}
