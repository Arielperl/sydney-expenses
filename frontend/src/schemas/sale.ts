import { z } from 'zod'

import { todayIsoDate } from '../lib/format'
import { PAYMENT_METHODS, TAX_TREATMENTS, TRANSACTION_CURRENCIES } from '../types/sale'

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
    // vat_amount is NOT a form field: it is always backend-computed from
    // gross_amount + tax_treatment (see app/services/tax/vat.py on the
    // backend) and never submitted by the client — SaleForm shows it as a
    // read-only, live-recalculated preview only.
    tax_treatment: z.enum(TAX_TREATMENTS).default('standard'),
    processing_fee: z.union([
      z.coerce.number({ message: 'validation.feeInvalid' }).min(0, 'validation.feeNegative'),
      z.literal(''),
      z.undefined(),
    ]),
    currency: z.enum(TRANSACTION_CURRENCIES, { message: 'validation.currencyInvalid' }).default('ILS'),
    sale_date: z
      .string()
      .min(1, 'validation.dateRequired')
      .refine((value) => value >= MIN_DATE, 'validation.dateTooOld')
      .refine(isNotInFuture, 'validation.dateFuture'),
    payment_method: z.enum(PAYMENT_METHODS).optional().or(z.literal('')),
    description: z.string().trim().max(2000, 'validation.descriptionTooLong').optional().or(z.literal('')),
  })

export type SaleFormValues = z.infer<typeof saleFormSchema>
export type SaleFormInput = z.input<typeof saleFormSchema>
