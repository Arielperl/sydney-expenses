import type { SupportRequest } from '../services/supportService'
import { parseServerTimestamp } from './supportTime'

const PROVIDER_LABELS: Record<string, string> = { grow: 'Grow', cardcom: 'Cardcom', tabit: 'Tabit', cal: 'כאל / Cal' }

export function providerLabel(provider: string): string {
  return PROVIDER_LABELS[provider] ?? provider
}

/** Open requests first, then the most recently updated. */
export function sortTickets(requests: SupportRequest[]): SupportRequest[] {
  return [...requests].sort((a, b) =>
    Number(b.status === 'open') - Number(a.status === 'open')
    || parseServerTimestamp(b.updated_at).getTime() - parseServerTimestamp(a.updated_at).getTime(),
  )
}
