import { useTranslation } from 'react-i18next'

import { colorForCategory } from '../lib/categoryColors'

export function CategoryBadge({ category }: { category: string }) {
  const { t } = useTranslation()
  const color = colorForCategory(category)
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium"
      style={{ backgroundColor: `${color}1a`, color }}
    >
      <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: color }} />
      {t(`categories.${category}`, category)}
    </span>
  )
}
