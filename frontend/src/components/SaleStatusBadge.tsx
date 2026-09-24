import { useTranslation } from 'react-i18next'

import type { SaleStatus } from '../types/sale'
import { Badge, type BadgeTone } from './ui'

const STATUS_TONES: Record<SaleStatus, BadgeTone> = {
  succeeded: 'success',
  pending: 'warning',
  failed: 'danger',
  refunded: 'neutral',
  partially_refunded: 'info',
}

export function SaleStatusBadge({ status }: { status: SaleStatus }) {
  const { t } = useTranslation()
  return <Badge tone={STATUS_TONES[status]}>{t(`saleStatus.${status}`)}</Badge>
}
