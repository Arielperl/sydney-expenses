import { useAuth } from '../contexts/AuthContext'
import { useTranslation } from 'react-i18next'

/** Displays the authenticated user's active business workspace. */
export function BusinessBadge() {
  const { user } = useAuth()
  const { t } = useTranslation()
  return (
    <span className="inline-flex w-fit items-center rounded-full bg-stone-100 px-2.5 py-1 text-xs font-medium text-stone-500 dark:bg-stone-800 dark:text-stone-400">
      {user?.business_name || t('common.businessBadge')}
    </span>
  )
}
