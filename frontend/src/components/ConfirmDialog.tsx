import { AlertTriangle } from 'lucide-react'
import { useEffect, useId, useRef } from 'react'
import { useTranslation } from 'react-i18next'

import { useDialogA11y } from '../hooks/useDialogA11y'
import { buttonClasses } from './ui-classes'

export function ConfirmDialog({
  title,
  description,
  confirmLabel,
  cancelLabel,
  isLoading = false,
  error,
  onConfirm,
  onClose,
}: {
  title: string
  description: string
  confirmLabel: string
  cancelLabel?: string
  isLoading?: boolean
  error?: string | null
  onConfirm: () => void
  onClose: () => void
}) {
  const { t } = useTranslation()
  const dialogRef = useRef<HTMLDivElement>(null)
  const cancelButtonRef = useRef<HTMLButtonElement>(null)
  const titleId = useId()
  const descriptionId = useId()

  useDialogA11y({ dialogRef, isLoading, onClose })
  useEffect(() => {
    cancelButtonRef.current?.focus()
  }, [])

  function handleClose() {
    if (isLoading) return
    onClose()
  }

  function handleConfirm() {
    if (isLoading) return
    onConfirm()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        type="button"
        aria-label={t('common.closeDialog')}
        className="absolute inset-0 animate-fade-in bg-zinc-950/45 backdrop-blur-[2px]"
        onClick={handleClose}
        tabIndex={-1}
      />
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        className="relative w-full max-w-md animate-pop-in rounded-2xl border border-zinc-200 bg-white p-6 shadow-raised dark:border-zinc-800 dark:bg-zinc-900"
      >
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-danger-50 ring-1 ring-danger-600/10 dark:bg-danger-500/10">
            <AlertTriangle size={18} className="text-danger-600 dark:text-danger-500" aria-hidden="true" />
          </div>
          <div className="min-w-0 flex-1 pt-1">
            <h2 id={titleId} className="text-base font-semibold text-zinc-900 dark:text-zinc-50">
              {title}
            </h2>
            <p id={descriptionId} className="mt-1.5 text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">
              {description}
            </p>
          </div>
        </div>

        {error && (
          <p role="alert" className="mt-4 rounded-lg bg-danger-50 px-3 py-2 text-sm text-danger-700 dark:bg-danger-500/10 dark:text-danger-500">
            {error}
          </p>
        )}

        <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <button
            ref={cancelButtonRef}
            type="button"
            disabled={isLoading}
            onClick={handleClose}
            className={buttonClasses('secondary')}
          >
            {cancelLabel ?? t('common.cancel')}
          </button>
          <button
            type="button"
            disabled={isLoading}
            onClick={handleConfirm}
            className={buttonClasses('danger')}
          >
            {isLoading ? t('common.deleting') : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
