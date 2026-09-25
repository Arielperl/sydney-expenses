import { useMutation } from '@tanstack/react-query'
import { useEffect, useId, useRef, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'

import { createSupportRequest, type SupportRequest } from '../../services/supportService'
import { FormField, inputClasses } from '../FormField'
import { Modal } from '../Modal'
import { buttonClasses } from '../ui-classes'
import { providerLabel } from '../../lib/support'

const SUBJECT_MAX = 160
const MESSAGE_MIN = 10
const MESSAGE_MAX = 5000
const PROVIDERS = ['grow', 'cardcom', 'tabit', 'cal'] as const

export function NewSupportRequestDialog({ onClose, onCreated }: { onClose: () => void; onCreated: (request: SupportRequest) => void }) {
  const { t } = useTranslation()
  const [subject, setSubject] = useState('')
  const [provider, setProvider] = useState('')
  const [message, setMessage] = useState('')
  const subjectRef = useRef<HTMLInputElement>(null)
  const subjectHintId = useId()
  const messageHintId = useId()
  const create = useMutation({ mutationFn: createSupportRequest, onSuccess: onCreated })

  useEffect(() => {
    subjectRef.current?.focus()
  }, [])

  function submit(event: FormEvent) {
    event.preventDefault()
    if (create.isPending) return
    create.mutate({ subject: subject.trim(), message: message.trim(), provider: provider || undefined })
  }

  function close() {
    if (!create.isPending) onClose()
  }

  return (
    <Modal title={t('support.form.title')} onClose={close}>
      <form onSubmit={submit} className="space-y-5">
        <p className="text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">{t('support.form.intro')}</p>
        <FormField label={t('support.form.subject')} htmlFor="support-subject">
          <input
            ref={subjectRef}
            id="support-subject"
            className={inputClasses}
            required
            minLength={3}
            maxLength={SUBJECT_MAX}
            value={subject}
            onChange={(event) => setSubject(event.target.value)}
            aria-describedby={subjectHintId}
            dir="auto"
            autoComplete="off"
          />
          <p id={subjectHintId} className="mt-1.5 flex justify-between gap-3 text-xs text-zinc-500 dark:text-zinc-400">
            <span>{t('support.form.subjectHint')}</span>
            <bdi dir="ltr" className="figure shrink-0">{t('support.form.characters', { count: subject.length, max: SUBJECT_MAX })}</bdi>
          </p>
        </FormField>
        <FormField label={t('support.form.provider')} htmlFor="support-provider">
          <select id="support-provider" value={provider} onChange={(event) => setProvider(event.target.value)} className={inputClasses}>
            <option value="">{t('support.form.providerNone')}</option>
            {PROVIDERS.map((value) => <option key={value} value={value}>{providerLabel(value)}</option>)}
          </select>
        </FormField>
        <FormField label={t('support.form.message')} htmlFor="support-message">
          <textarea
            id="support-message"
            className={`${inputClasses} min-h-36 resize-y leading-relaxed`}
            required
            minLength={MESSAGE_MIN}
            maxLength={MESSAGE_MAX}
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            aria-describedby={messageHintId}
            dir="auto"
          />
          <p id={messageHintId} className="mt-1.5 flex justify-between gap-3 text-xs text-zinc-500 dark:text-zinc-400">
            <span>{t('support.form.messageHint')}</span>
            <bdi dir="ltr" className="figure shrink-0">{t('support.form.characters', { count: message.length, max: MESSAGE_MAX })}</bdi>
          </p>
        </FormField>
        {create.isError && (
          <p role="alert" className="rounded-lg bg-danger-50 px-3 py-2 text-sm text-danger-700 dark:bg-danger-500/10 dark:text-danger-500">
            {create.error.message}
          </p>
        )}
        <div className="flex flex-col-reverse gap-2 border-t border-zinc-100 pt-4 sm:flex-row sm:justify-end dark:border-zinc-800">
          <button type="button" disabled={create.isPending} className={buttonClasses('secondary')} onClick={close}>
            {t('support.form.cancel')}
          </button>
          <button type="submit" disabled={create.isPending} className={buttonClasses('primary')}>
            {create.isPending ? t('support.form.submitting') : t('support.form.submit')}
          </button>
        </div>
      </form>
    </Modal>
  )
}
