import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

interface AttentionItem {
  key: string
  count: number
  label: string
  severity: 'danger' | 'amber'
  to: string
}

const SEVERITY_STYLES: Record<AttentionItem['severity'], string> = {
  danger: 'bg-danger-500/10 text-danger-700 dark:text-danger-400',
  amber: 'bg-amber-500/10 text-amber-700 dark:text-amber-400',
}

export function NeedsAttentionPanel({
  pendingDocumentsCount,
  documentFailuresCount,
  incompleteDetailsCount,
}: {
  pendingDocumentsCount: number
  documentFailuresCount: number
  incompleteDetailsCount: number
}) {
  const { t } = useTranslation()

  const items = ([
    {
      key: 'pendingDocuments',
      count: pendingDocumentsCount,
      label: t('dashboard.attention.pendingDocuments', { count: pendingDocumentsCount }),
      severity: 'amber',
      to: '/exceptions?category=pendingDocuments',
    },
    {
      key: 'documentFailures',
      count: documentFailuresCount,
      label: t('dashboard.attention.documentFailures', { count: documentFailuresCount }),
      severity: 'danger',
      to: '/exceptions?category=documentFailures',
    },
    {
      key: 'incompleteDetails',
      count: incompleteDetailsCount,
      label: t('dashboard.attention.incompleteDetails', { count: incompleteDetailsCount }),
      severity: 'amber',
      to: '/exceptions?category=incompleteDetails',
    },
  ] satisfies AttentionItem[]).filter((item) => item.count > 0)

  return (
    <div className="flex h-full flex-col rounded-xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
      <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">{t('dashboard.needsAttention')}</h2>

      {items.length === 0 ? (
        <div className="mt-4 flex flex-1 flex-col items-center justify-center rounded-lg bg-success-500/10 px-4 py-8 text-center">
          <span className="text-2xl" aria-hidden="true">
            ✓
          </span>
          <p className="mt-2 text-sm font-semibold text-success-700 dark:text-success-400">
            {t('dashboard.allClear')}
          </p>
        </div>
      ) : (
        <ul className="mt-4 space-y-2">
          {items.map((item) => (
            <li key={item.key}>
              <Link
                to={item.to}
                className="flex items-center justify-between gap-3 rounded-lg border border-zinc-200 px-3 py-2.5 text-sm hover:bg-zinc-50 dark:border-zinc-800 dark:hover:bg-zinc-800/60"
              >
                <span className="font-medium text-zinc-700 dark:text-zinc-200">{item.label}</span>
                <span
                  className={`inline-flex min-w-[1.75rem] items-center justify-center rounded-full px-2 py-0.5 text-xs font-bold ${SEVERITY_STYLES[item.severity]}`}
                >
                  {item.count}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
