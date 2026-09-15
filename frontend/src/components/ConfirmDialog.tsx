import { AlertTriangle } from 'lucide-react'
import { useEffect, useId, useRef } from 'react'
import { useTranslation } from 'react-i18next'

const FOCUSABLE_SELECTOR =
  'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

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
  const previouslyFocused = useRef<HTMLElement | null>(null)
  const titleId = useId()
  const descriptionId = useId()

  useEffect(() => {
    previouslyFocused.current = document.activeElement as HTMLElement | null
    cancelButtonRef.current?.focus()
    return () => {
      previouslyFocused.current?.focus?.()
    }
    // Runs once on mount/unmount only — capturing and restoring focus should
    // not re-trigger when isLoading or other props change mid-dialog.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        if (isLoading) return
        event.preventDefault()
        onClose()
        return
      }
      if (event.key !== 'Tab' || !dialogRef.current) return
      const focusable = Array.from(dialogRef.current.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR))
      if (focusable.length === 0) return
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [isLoading, onClose])

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
        className="absolute inset-0 bg-stone-900/50"
        onClick={handleClose}
        tabIndex={-1}
      />
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        className="relative w-full max-w-md rounded-2xl bg-white p-6 shadow-xl dark:bg-stone-900"
      >
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-amber-50 dark:bg-amber-500/10">
            <AlertTriangle size={20} className="text-amber-600 dark:text-amber-400" />
          </div>
          <div className="min-w-0 flex-1 pt-1">
            <h2 id={titleId} className="text-lg font-semibold text-stone-900 dark:text-stone-100">
              {title}
            </h2>
            <p id={descriptionId} className="mt-1 text-sm text-stone-600 dark:text-stone-400">
              {description}
            </p>
          </div>
        </div>

        {error && (
          <p role="alert" className="mt-3 text-sm text-danger-600 dark:text-danger-400">
            {error}
          </p>
        )}

        <div className="mt-5 flex justify-end gap-2">
          <button
            ref={cancelButtonRef}
            type="button"
            disabled={isLoading}
            onClick={handleClose}
            className="rounded-md border border-stone-300 px-4 py-2 text-sm font-medium text-stone-700 hover:bg-stone-50 disabled:opacity-60 dark:border-stone-700 dark:text-stone-200 dark:hover:bg-stone-800"
          >
            {cancelLabel ?? t('common.cancel')}
          </button>
          <button
            type="button"
            disabled={isLoading}
            onClick={handleConfirm}
            className="rounded-md bg-danger-600 px-4 py-2 text-sm font-semibold text-white hover:bg-danger-700 disabled:opacity-60"
          >
            {isLoading ? t('common.deleting') : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
