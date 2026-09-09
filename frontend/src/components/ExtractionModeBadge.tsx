import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { getSystemCapabilities } from '../services/systemService'
import type { SystemCapabilities } from '../types/system'

const BADGE_STYLES: Record<SystemCapabilities['receipt_extraction_mode'], { badge: string; dot: string }> = {
  demo: { badge: 'bg-stone-100 text-stone-600 dark:bg-stone-800 dark:text-stone-300', dot: 'bg-stone-400' },
  local: { badge: 'bg-brand-50 text-brand-700 dark:bg-brand-500/10 dark:text-brand-400', dot: 'bg-brand-500' },
  ai: { badge: 'bg-success-50 text-success-700 dark:bg-success-500/10 dark:text-success-400', dot: 'bg-success-500' },
}

export function ExtractionModeBadge() {
  const { t } = useTranslation()
  // Defaults to "demo" while loading or on error — the safe direction is to
  // never claim real AI extraction is active unless the backend confirms it.
  const { data } = useQuery({
    queryKey: ['system-capabilities'],
    queryFn: getSystemCapabilities,
    staleTime: Infinity,
    retry: 1,
  })
  const mode = data?.receipt_extraction_mode ?? 'demo'
  const styles = BADGE_STYLES[mode]

  return (
    <span className={['inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium', styles.badge].join(' ')}>
      <span aria-hidden="true" className={['h-1.5 w-1.5 rounded-full', styles.dot].join(' ')} />
      {t(`uploadReceipt.mode.${mode}`)}
    </span>
  )
}
