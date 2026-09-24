import { useTranslation } from 'react-i18next'

import type { DocumentStatus } from '../types/sale'
import { Badge, type BadgeTone } from './ui'

const STATUS_TONES: Record<DocumentStatus, BadgeTone> = {
  pending: 'warning',
  waiting_automatic: 'info',
  issued: 'success',
  failed: 'danger',
  not_required: 'neutral',
}

export function DocumentStatusBadge({ status }: { status: DocumentStatus }) {
  const { t } = useTranslation()
  return <Badge tone={STATUS_TONES[status]}>{t(`documentStatus.${status}`)}</Badge>
}
