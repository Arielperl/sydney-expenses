import { Building2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import { useAuth } from '../contexts/AuthContext'

/** Displays the authenticated user's active business workspace. */
export function BusinessBadge() {
  const { user } = useAuth()
  const { t } = useTranslation()
  const name = user?.business_name || t('common.businessBadge')
  return (
    <div className="flex items-center gap-2.5 rounded-lg border border-zinc-200 bg-zinc-50 px-2.5 py-2 dark:border-zinc-800 dark:bg-zinc-950/40" title={name}>
      <Building2 className="h-4 w-4 shrink-0 text-zinc-500 dark:text-zinc-400" aria-hidden="true" />
      <span className="min-w-0 flex-1 truncate text-xs font-medium text-zinc-700 dark:text-zinc-300">{name}</span>
    </div>
  )
}
