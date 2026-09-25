import { X } from 'lucide-react'
import type { ReactNode } from 'react'
import { useEffect, useId, useRef } from 'react'
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

  useEffect(() => {
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = previousOverflow
    }
  }, [])

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center overflow-hidden p-0 sm:items-center sm:p-4">
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
        className="relative flex max-h-[calc(100dvh-1rem)] w-full max-w-lg animate-pop-in flex-col overflow-hidden rounded-t-2xl border border-zinc-200 bg-white shadow-raised sm:max-h-[calc(100dvh-2rem)] sm:rounded-2xl dark:border-zinc-800 dark:bg-zinc-900"
      >
        <div className="flex shrink-0 items-start justify-between gap-4 border-b border-zinc-100 px-5 py-4 sm:px-6 dark:border-zinc-800">
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
        <div className="min-h-0 overscroll-contain overflow-y-auto px-5 py-5 sm:px-6">
          {children}
        </div>
      </div>
    </div>
  )
}
