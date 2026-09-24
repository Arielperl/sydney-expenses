import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { getSystemCapabilities } from '../services/systemService'
import type { SystemCapabilities } from '../types/system'
import { Badge, type BadgeTone } from './ui'

const MODE_TONES: Record<SystemCapabilities['receipt_extraction_mode'], BadgeTone> = {
  demo: 'neutral',
  local: 'brand',
  ai: 'success',
}

export function ExtractionModeBadge() {
  const { t } = useTranslation()
  const { data } = useQuery({
    queryKey: ['system-capabilities'],
    queryFn: getSystemCapabilities,
    staleTime: Infinity,
    retry: 1,
  })
  // Do not show a misleading mode while capabilities are loading or if the
  // backend cannot confirm which extractor is active.
  if (!data) return null

  const mode = data.receipt_extraction_mode
  return <Badge tone={MODE_TONES[mode]}>{t(`uploadReceipt.mode.${mode}`)}</Badge>
}
