import { useAuth } from '../contexts/AuthContext'
import { useTranslation } from 'react-i18next'

/** A small, honest disclosure that this workspace is one fixed fictional
 * Israeli demo business — not a real, configurable multi-business product
 * yet. See backend app/domain/demo_business.py, the single source of truth
 * this text describes. */
export function DemoBusinessBadge() {
  const { user } = useAuth()
  const { t } = useTranslation()
  return (
    <span className="inline-flex w-fit items-center rounded-full bg-stone-100 px-2.5 py-1 text-xs font-medium text-stone-500 dark:bg-stone-800 dark:text-stone-400">
      {user?.business_name || t('common.demoBusinessBadge')}
    </span>
  )
}
