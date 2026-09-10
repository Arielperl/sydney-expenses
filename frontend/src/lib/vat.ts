import type { TaxTreatment } from '../types/sale'

// Mirrors backend/app/services/tax/vat.py — this is a PREVIEW only, shown
// in the form before the user saves. The backend independently recomputes
// and is the sole source of truth for what actually gets persisted; this
// value is never sent to the API.
export const STANDARD_VAT_RATE = 0.18

export function previewVat(grossAmount: number, taxTreatment: TaxTreatment): number {
  if (!Number.isFinite(grossAmount) || grossAmount < 0) return 0
  if (taxTreatment === 'zero_rate' || taxTreatment === 'exempt') return 0
  const vat = (grossAmount * STANDARD_VAT_RATE) / (1 + STANDARD_VAT_RATE)
  return Math.round(vat * 100) / 100
}
