import { ChevronLeft, CircleCheck, FileClock, FileWarning, ReceiptText } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { Card, CardHeader } from '../ui'
import { cx } from '../ui-classes'

interface AttentionItem {
  key: string
  count: number
  label: string
  severity: 'danger' | 'amber'
  to: string
  icon: typeof FileClock
}

const SEVERITY_STYLES: Record<AttentionItem['severity'], { icon: string; count: string }> = {
  danger: { icon: 'bg-danger-50 text-danger-700 dark:bg-danger-500/10 dark:text-danger-500', count: 'text-danger-700 dark:text-danger-500' },
  amber: { icon: 'bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300', count: 'text-amber-800 dark:text-amber-300' },
}

export function NeedsAttentionPanel({
  className,
  pendingDocumentsCount,
  documentFailuresCount,
  incompleteDetailsCount,
}: {
  className?: string
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
      icon: FileClock,
    },
    {
      key: 'documentFailures',
      count: documentFailuresCount,
      label: t('dashboard.attention.documentFailures', { count: documentFailuresCount }),
      severity: 'danger',
      to: '/exceptions?category=documentFailures',
      icon: FileWarning,
    },
    {
      key: 'incompleteDetails',
      count: incompleteDetailsCount,
      label: t('dashboard.attention.incompleteDetails', { count: incompleteDetailsCount }),
      severity: 'amber',
      to: '/exceptions?category=incompleteDetails',
      icon: ReceiptText,
    },
  ] satisfies AttentionItem[]).filter((item) => item.count > 0)

  return (
    <Card className={cx('flex flex-col', className)} aria-labelledby="attention-title">
      <CardHeader id="attention-title" title={t('dashboard.needsAttention')} description={t('dashboard.attentionDescription')} />

      {items.length === 0 ? (
        <div className="m-5 flex flex-1 flex-col items-center justify-center rounded-lg bg-success-50/70 px-4 py-8 text-center dark:bg-success-500/10">
          <CircleCheck className="h-6 w-6 text-success-600 dark:text-success-500" aria-hidden="true" />
          <p className="mt-2 text-sm font-medium text-success-700 dark:text-success-500">{t('dashboard.allClear')}</p>
        </div>
      ) : (
        <ul className="mt-3 flex-1 space-y-1 px-2.5 pb-3">
          {items.map((item) => (
            <li key={item.key}>
              <Link
                to={item.to}
                className="group flex items-center gap-3 rounded-lg px-2.5 py-2.5 text-sm transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-800/60"
              >
                <span className={cx('grid h-8 w-8 shrink-0 place-items-center rounded-lg', SEVERITY_STYLES[item.severity].icon)} aria-hidden="true">
                  <item.icon className="h-4 w-4" />
                </span>
                <span className="min-w-0 flex-1 font-medium text-zinc-800 dark:text-zinc-200">{item.label}</span>
                <ChevronLeft className="h-4 w-4 shrink-0 text-zinc-400 transition-transform group-hover:-translate-x-0.5 ltr:rotate-180 ltr:group-hover:translate-x-0.5" aria-hidden="true" />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}
