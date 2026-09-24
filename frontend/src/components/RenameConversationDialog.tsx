import { Pencil } from 'lucide-react'
import { useEffect, useId, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { useDialogA11y } from '../hooks/useDialogA11y'
import { buttonClasses } from './ui-classes'

export const CONVERSATION_TITLE_MAX_LENGTH = 80

export function RenameConversationDialog({
  currentTitle,
  isLoading = false,
  error,
  onSave,
  onClose,
}: {
  currentTitle: string
  isLoading?: boolean
  error?: string | null
  onSave: (title: string) => void
  onClose: () => void
}) {
  const { t } = useTranslation()
  const [value, setValue] = useState(currentTitle)
  const dialogRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const titleId = useId()
  const descriptionId = useId()

  useDialogA11y({ dialogRef, isLoading, onClose })
  useEffect(() => {
    inputRef.current?.focus()
    inputRef.current?.select()
  }, [])

  const trimmed = value.trim()
  const isUnchanged = trimmed === currentTitle.trim()
  const isValid = trimmed.length > 0 && trimmed.length <= CONVERSATION_TITLE_MAX_LENGTH

  function handleClose() {
    if (isLoading) return
    onClose()
  }

  function handleSubmit() {
    if (isLoading || !isValid) return
    if (isUnchanged) {
      onClose()
      return
    }
    onSave(trimmed)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        type="button"
        aria-label={t('common.closeDialog')}
        className="absolute inset-0 bg-zinc-900/50"
        onClick={handleClose}
        tabIndex={-1}
      />
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        className="relative w-full max-w-md rounded-2xl bg-white p-6 shadow-xl dark:bg-zinc-900"
      >
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand-50 dark:bg-brand-500/10">
            <Pencil size={18} className="text-brand-600 dark:text-brand-400" />
          </div>
          <div className="min-w-0 flex-1 pt-1">
            <h2 id={titleId} className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
              {t('assistant.renameConversation')}
            </h2>
            <p id={descriptionId} className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
              {t('assistant.renameDescription')}
            </p>
          </div>
        </div>

        <form
          className="mt-4"
          onSubmit={(event) => {
            event.preventDefault()
            handleSubmit()
          }}
        >
          <label htmlFor={`${titleId}-input`} className="sr-only">
            {t('assistant.renameConversation')}
          </label>
          <input
            ref={inputRef}
            id={`${titleId}-input`}
            type="text"
            value={value}
            disabled={isLoading}
            maxLength={CONVERSATION_TITLE_MAX_LENGTH + 20}
            onChange={(event) => setValue(event.target.value)}
            className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none disabled:opacity-60 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
          />

          {!isValid && trimmed.length === 0 && value.length > 0 && (
            <p className="mt-2 text-xs text-zinc-500 dark:text-zinc-400">{t('assistant.renameEmptyHint')}</p>
          )}
          {trimmed.length > CONVERSATION_TITLE_MAX_LENGTH && (
            <p className="mt-2 text-xs text-danger-600 dark:text-danger-500">
              {t('assistant.renameTooLongHint', { max: CONVERSATION_TITLE_MAX_LENGTH })}
            </p>
          )}
          {error && (
            <p role="alert" className="mt-2 text-sm text-danger-600 dark:text-danger-500">
              {error}
            </p>
          )}

          <div className="mt-5 flex justify-end gap-2">
            <button
              type="button"
              disabled={isLoading}
              onClick={handleClose}
              className={buttonClasses('secondary')}
            >
              {t('common.cancel')}
            </button>
            <button
              type="submit"
              disabled={isLoading || !isValid}
              className={buttonClasses('primary')}
            >
              {isLoading ? t('common.saving') : t('assistant.saveNewTitle')}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
