import { useAuth } from '../contexts/AuthContext'
import { useTranslation } from 'react-i18next'

/** Displays the authenticated user's active business workspace. */
export function BusinessBadge() {
  const { user } = useAuth()
  const { t } = useTranslation()
  return (
    <span className="inline-flex w-fit items-center rounded-full bg-zinc-100 px-2.5 py-1 text-xs font-medium text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400">
      {user?.business_name || t('common.businessBadge')}
    </span>
  )
}
