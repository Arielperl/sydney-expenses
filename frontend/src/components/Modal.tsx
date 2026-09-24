import { X } from 'lucide-react'
import type { ReactNode } from 'react'
import { useId, useRef } from 'react'
import { useTranslation } from 'react-i18next'

import { useDialogA11y } from '../hooks/useDialogA11y'

export function Modal({
  title,
  onClose,
  children,
}: {
  title: string
  onClose: () => void
  children: ReactNode
}) {
  const { t } = useTranslation()
  const dialogRef = useRef<HTMLDivElement>(null)
  const titleId = useId()
  useDialogA11y({ dialogRef, isLoading: false, onClose })

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center p-0 sm:items-center sm:p-4">
      <button
        aria-label={t('common.closeDialog')}
        className="absolute inset-0 animate-fade-in bg-zinc-950/45 backdrop-blur-[2px]"
        onClick={onClose}
        tabIndex={-1}
      />
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="relative max-h-[92vh] w-full max-w-lg animate-pop-in overflow-y-auto rounded-t-2xl border border-zinc-200 bg-white p-6 shadow-raised sm:rounded-2xl dark:border-zinc-800 dark:bg-zinc-900"
      >
        <div className="mb-5 flex items-start justify-between gap-4">
          <h2 id={titleId} className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">
            {title}
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label={t('common.close')}
            className="-m-1.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg text-zinc-500 hover:bg-zinc-100 hover:text-zinc-800 dark:hover:bg-zinc-800 dark:hover:text-zinc-200"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}
