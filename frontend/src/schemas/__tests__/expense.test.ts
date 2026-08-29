import { describe, expect, it } from 'vitest'

import { expenseFormSchema } from '../expense'
import { todayIsoDate } from '../../lib/format'

function validPayload(overrides: Record<string, unknown> = {}) {
  return {
    business_name: 'Shufersal',
    receipt_number: '',
    amount: 100,
    vat_amount: '',
    currency: 'ILS',
    category: 'groceries',
    expense_date: todayIsoDate(),
    payment_method: '',
    notes: '',
    ...overrides,
  }
}

describe('expenseFormSchema', () => {
  it('accepts a valid manual expense', () => {
    const result = expenseFormSchema.safeParse(validPayload())
    expect(result.success).toBe(true)
  })

  it('rejects a blank business name', () => {
    const result = expenseFormSchema.safeParse(validPayload({ business_name: '   ' }))
    expect(result.success).toBe(false)
    expect(result.error?.issues[0]?.message).toBe('validation.businessNameRequired')
  })

  it('rejects a negative amount', () => {
    const result = expenseFormSchema.safeParse(validPayload({ amount: -5 }))
    expect(result.success).toBe(false)
    expect(result.error?.issues[0]?.message).toBe('validation.amountNegative')
  })

  it('rejects a future expense date', () => {
    const future = new Date()
    future.setDate(future.getDate() + 5)
    const isoFuture = future.toISOString().slice(0, 10)
    const result = expenseFormSchema.safeParse(validPayload({ expense_date: isoFuture }))
    expect(result.success).toBe(false)
    expect(result.error?.issues[0]?.message).toBe('validation.dateFuture')
  })

  it('rejects a currency that is not 3 letters', () => {
    const result = expenseFormSchema.safeParse(validPayload({ currency: 'IL' }))
    expect(result.success).toBe(false)
    expect(result.error?.issues[0]?.message).toBe('validation.currencyLength')
  })

  it('rejects VAT greater than the amount', () => {
    const result = expenseFormSchema.safeParse(validPayload({ amount: 10, vat_amount: 20 }))
    expect(result.success).toBe(false)
    expect(result.error?.issues[0]?.message).toBe('validation.vatExceedsAmount')
  })

  it('allows an empty VAT amount', () => {
    const result = expenseFormSchema.safeParse(validPayload({ vat_amount: '' }))
    expect(result.success).toBe(true)
  })
})
