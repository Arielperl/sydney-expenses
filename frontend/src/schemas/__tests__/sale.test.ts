import { describe, expect, it } from 'vitest'

import { saleFormSchema } from '../sale'

function validInput(overrides: Record<string, unknown> = {}) {
  return {
    customer_name: 'Dana Cohen',
    customer_contact: 'dana@example.com',
    service_name: 'Consulting session',
    gross_amount: 100,
    tax_treatment: 'standard',
    processing_fee: 3,
    currency: 'ILS',
    sale_date: '2026-01-01',
    payment_method: 'card',
    description: '',
    ...overrides,
  }
}

describe('saleFormSchema', () => {
  it('accepts a fully valid input', () => {
    const result = saleFormSchema.safeParse(validInput())
    expect(result.success).toBe(true)
  })

  it('rejects a blank customer name', () => {
    const result = saleFormSchema.safeParse(validInput({ customer_name: '  ' }))
    expect(result.success).toBe(false)
  })

  it('rejects a blank service name', () => {
    const result = saleFormSchema.safeParse(validInput({ service_name: '' }))
    expect(result.success).toBe(false)
  })

  it('rejects an empty gross_amount instead of silently coercing to 0', () => {
    const result = saleFormSchema.safeParse(validInput({ gross_amount: '' }))
    expect(result.success).toBe(false)
  })

  it('rejects a negative gross_amount', () => {
    const result = saleFormSchema.safeParse(validInput({ gross_amount: -10 }))
    expect(result.success).toBe(false)
  })

  it('allows an empty processing_fee', () => {
    const result = saleFormSchema.safeParse(validInput({ processing_fee: '' }))
    expect(result.success).toBe(true)
  })

  it('defaults tax_treatment to standard when omitted', () => {
    const { tax_treatment: _omit, ...rest } = validInput()
    const result = saleFormSchema.safeParse(rest)
    expect(result.success).toBe(true)
    if (result.success) expect(result.data.tax_treatment).toBe('standard')
  })

  it('rejects an invalid tax_treatment value', () => {
    const result = saleFormSchema.safeParse(validInput({ tax_treatment: 'luxury_tax' }))
    expect(result.success).toBe(false)
  })

  it('accepts each supported currency', () => {
    for (const currency of ['ILS', 'USD', 'EUR']) {
      const result = saleFormSchema.safeParse(validInput({ currency }))
      expect(result.success).toBe(true)
    }
  })

  it('rejects a currency outside the supported set', () => {
    const result = saleFormSchema.safeParse(validInput({ currency: 'GBP' }))
    expect(result.success).toBe(false)
  })

  it('rejects a future sale date', () => {
    const result = saleFormSchema.safeParse(validInput({ sale_date: '2999-01-01' }))
    expect(result.success).toBe(false)
  })

  it('rejects a sale date before the minimum allowed date', () => {
    const result = saleFormSchema.safeParse(validInput({ sale_date: '1999-01-01' }))
    expect(result.success).toBe(false)
  })
})
