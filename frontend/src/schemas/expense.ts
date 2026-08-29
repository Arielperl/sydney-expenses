import { z } from 'zod'

import { EXPENSE_CATEGORIES } from '../types/expense'
import { todayIsoDate } from '../lib/format'

const MIN_DATE = '2000-01-01'

function isNotInFuture(value: string): boolean {
  return value <= todayIsoDate()
}

export const expenseFormSchema = z
  .object({
    business_name: z
      .string()
      .trim()
      .min(1, 'validation.businessNameRequired')
      .max(255, 'validation.businessNameTooLong'),
    receipt_number: z.string().trim().max(100, 'validation.receiptNumberTooLong').optional().or(z.literal('')),
    amount: z.coerce
      .number({ message: 'validation.amountInvalid' })
      .min(0, 'validation.amountNegative'),
    vat_amount: z.union([
      z.coerce.number({ message: 'validation.vatInvalid' }).min(0, 'validation.vatNegative'),
      z.literal(''),
      z.undefined(),
    ]),
    currency: z.string().trim().length(3, 'validation.currencyLength').default('ILS'),
    category: z.enum(EXPENSE_CATEGORIES),
    expense_date: z
      .string()
      .min(1, 'validation.dateRequired')
      .refine((value) => value >= MIN_DATE, 'validation.dateTooOld')
      .refine(isNotInFuture, 'validation.dateFuture'),
    payment_method: z.string().trim().max(50, 'validation.paymentMethodTooLong').optional().or(z.literal('')),
    notes: z.string().trim().max(1000, 'validation.notesTooLong').optional().or(z.literal('')),
  })
  .superRefine((values, ctx) => {
    if (values.vat_amount !== '' && values.vat_amount !== undefined && values.vat_amount > values.amount) {
      ctx.addIssue({
        code: 'custom',
        path: ['vat_amount'],
        message: 'validation.vatExceedsAmount',
      })
    }
  })

export type ExpenseFormValues = z.infer<typeof expenseFormSchema>
export type ExpenseFormInput = z.input<typeof expenseFormSchema>
