import { z } from 'zod'

import { todayIsoDate } from '../lib/format'
import { PAYMENT_METHODS } from '../types/sale'

const MIN_DATE = '2000-01-01'

function isNotInFuture(value: string): boolean {
  return value <= todayIsoDate()
}

export const saleFormSchema = z
  .object({
    customer_name: z
      .string()
      .trim()
      .min(1, 'validation.customerNameRequired')
      .max(255, 'validation.customerNameTooLong'),
    customer_contact: z.string().trim().max(255, 'validation.customerContactTooLong').optional().or(z.literal('')),
    service_name: z
      .string()
      .trim()
      .min(1, 'validation.serviceNameRequired')
      .max(255, 'validation.serviceNameTooLong'),
    // An empty string must never silently coerce to 0 (JavaScript's Number('')
    // is 0, not NaN) — it is remapped to undefined first, which z.number()
    // correctly rejects as invalid, so a still-unknown amount visibly blocks
    // submission instead of quietly saving as a zero-amount sale.
    gross_amount: z.preprocess(
      (value) => (value === '' ? undefined : value),
      z.coerce.number({ message: 'validation.amountInvalid' }).min(0, 'validation.amountNegative'),
    ),
    vat_amount: z.union([
      z.coerce.number({ message: 'validation.vatInvalid' }).min(0, 'validation.vatNegative'),
      z.literal(''),
      z.undefined(),
    ]),
    processing_fee: z.union([
      z.coerce.number({ message: 'validation.feeInvalid' }).min(0, 'validation.feeNegative'),
      z.literal(''),
      z.undefined(),
    ]),
    currency: z.string().trim().length(3, 'validation.currencyLength').default('ILS'),
    sale_date: z
      .string()
      .min(1, 'validation.dateRequired')
      .refine((value) => value >= MIN_DATE, 'validation.dateTooOld')
      .refine(isNotInFuture, 'validation.dateFuture'),
    payment_method: z.enum(PAYMENT_METHODS).optional().or(z.literal('')),
    description: z.string().trim().max(2000, 'validation.descriptionTooLong').optional().or(z.literal('')),
  })
  .superRefine((values, ctx) => {
    if (values.vat_amount !== '' && values.vat_amount !== undefined && values.vat_amount > values.gross_amount) {
      ctx.addIssue({
        code: 'custom',
        path: ['vat_amount'],
        message: 'validation.vatExceedsAmount',
      })
    }
  })

export type SaleFormValues = z.infer<typeof saleFormSchema>
export type SaleFormInput = z.input<typeof saleFormSchema>
