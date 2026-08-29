import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { getSystemCapabilities } from '../services/systemService'

export function ExtractionModeBadge() {
  const { t } = useTranslation()
  // Defaults to "demo" while loading or on error — the safe direction is to
  // never claim AI extraction is active unless the backend confirms it.
  const { data } = useQuery({
    queryKey: ['system-capabilities'],
    queryFn: getSystemCapabilities,
    staleTime: Infinity,
    retry: 1,
  })
  const mode = data?.receipt_extraction_mode ?? 'demo'
  const isAi = mode === 'ai'

  return (
    <span
      className={[
        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium',
        isAi ? 'bg-success-50 text-success-700' : 'bg-slate-100 text-slate-600',
      ].join(' ')}
    >
      <span
        aria-hidden="true"
        className={['h-1.5 w-1.5 rounded-full', isAi ? 'bg-success-500' : 'bg-slate-400'].join(' ')}
      />
      {t(`uploadReceipt.mode.${mode}`)}
    </span>
  )
}
