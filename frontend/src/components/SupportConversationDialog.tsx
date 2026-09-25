import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Send, X } from 'lucide-react'
import { useEffect, useId, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

import { useDialogA11y } from '../hooks/useDialogA11y'
import {
  listSupportMessages,
  sendSupportMessage,
  type SupportRequest,
} from '../services/supportService'
import { buttonClasses, cx } from './ui-classes'

export function SupportConversationDialog({
  request,
  staff,
  english = false,
  onClose,
  actions,
}: {
  request: SupportRequest
  staff: boolean
  english?: boolean
  onClose: () => void
  actions?: ReactNode
}) {
  const queryClient = useQueryClient()
  const [body, setBody] = useState('')
  const dialogRef = useRef<HTMLDivElement>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const titleId = useId()
  useDialogA11y({ dialogRef, isLoading: false, onClose })

  const queryKey = ['support-messages', staff ? 'staff' : 'customer', request.id]
  const messages = useQuery({
    queryKey,
    queryFn: () => listSupportMessages(request.id, staff),
    refetchInterval: 10_000,
  })
  const send = useMutation({
    mutationFn: (message: string) => sendSupportMessage(request.id, message, staff),
    onSuccess: () => {
      setBody('')
      void queryClient.invalidateQueries({ queryKey })
      void queryClient.invalidateQueries({ queryKey: [staff ? 'staff-requests' : 'support-requests-own'] })
    },
  })

  useEffect(() => {
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = previousOverflow }
  }, [])

  useEffect(() => {
    if (messages.data) messagesEndRef.current?.scrollIntoView({ block: 'end' })
  }, [messages.data])

  function submit(event: FormEvent) {
    event.preventDefault()
    const message = body.trim()
    if (message) send.mutate(message)
  }

  return createPortal(<div className="fixed inset-0 z-50 h-[100dvh] w-screen overflow-hidden bg-white dark:bg-zinc-950">
    <div ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby={titleId} className="flex h-full min-h-0 flex-col overflow-hidden">
      <header className="flex shrink-0 items-center justify-between gap-4 border-b border-zinc-200 px-4 py-3 sm:px-6 dark:border-zinc-800">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h2 id={titleId} className="truncate text-lg font-semibold text-zinc-900 dark:text-zinc-50">{request.subject}</h2>
            <span className={cx('shrink-0 rounded-full px-2 py-0.5 text-xs font-medium', request.status === 'open' ? 'bg-amber-50 text-amber-800 dark:bg-amber-500/10 dark:text-amber-300' : 'bg-success-50 text-success-700 dark:bg-success-500/10 dark:text-success-500')}>{request.status === 'open' ? (english ? 'Open' : 'פתוחה') : (english ? 'Resolved' : 'טופלה')}</span>
          </div>
          {staff && <p className="truncate text-sm text-zinc-500">{request.business_name} · <span dir="ltr">{request.requester_email}</span></p>}
        </div>
        <div className="flex shrink-0 items-center gap-2">{actions}<button type="button" aria-label={english ? 'Close conversation' : 'סגירת השיחה'} onClick={onClose} className="grid h-10 w-10 place-items-center rounded-lg text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900 dark:hover:bg-zinc-800 dark:hover:text-zinc-100"><X className="h-5 w-5" aria-hidden="true" /></button></div>
      </header>

      <div className="min-h-0 flex-1 overscroll-contain overflow-y-auto bg-zinc-50 px-4 py-6 sm:px-8 dark:bg-zinc-950">
        <div className="mx-auto flex w-full max-w-4xl flex-col gap-4">
          {messages.isLoading && <p role="status" className="text-center text-sm text-zinc-500">{english ? 'Loading conversation…' : 'טוענים את השיחה…'}</p>}
          {messages.isError && <p role="alert" className="text-center text-sm text-danger-700">{english ? 'Could not load the conversation.' : 'לא ניתן לטעון את השיחה.'}</p>}
          {messages.data?.map(message => {
            const ownSide = staff ? message.author_type === 'staff' : message.author_type === 'customer'
            return <article key={message.id} className={cx('flex', ownSide ? 'justify-end' : 'justify-start')}>
              <div className={cx('max-w-[min(85%,42rem)] rounded-2xl px-4 py-3 shadow-card', ownSide ? 'rounded-br-md bg-brand-700 text-white' : 'rounded-bl-md border border-zinc-200 bg-white text-zinc-900 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-100')}>
                <div className={cx('mb-1 flex flex-wrap items-center gap-x-2 text-xs', ownSide ? 'text-white/75' : 'text-zinc-500')}><span>{ownSide ? (english ? 'You' : 'אתם') : (message.author_type === 'staff' ? (english ? 'Sydney support' : 'תמיכת Sydney') : message.author_name)}</span><time dateTime={message.created_at}>{new Date(message.created_at).toLocaleString(english ? 'en-US' : 'he-IL')}</time></div>
                <p className="whitespace-pre-wrap text-sm leading-6">{message.body}</p>
              </div>
            </article>
          })}
          <div ref={messagesEndRef} />
        </div>
      </div>

      <form onSubmit={submit} className="shrink-0 border-t border-zinc-200 bg-white px-4 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] sm:px-6 dark:border-zinc-800 dark:bg-zinc-900">
        <div className="mx-auto flex max-w-4xl items-end gap-2">
          <label htmlFor={`support-reply-${request.id}`} className="sr-only">{english ? 'Write a reply' : 'כתיבת תגובה'}</label>
          <textarea id={`support-reply-${request.id}`} rows={2} maxLength={5000} value={body} onChange={event => setBody(event.target.value)} placeholder={english ? 'Write a message…' : 'כתבו הודעה…'} className="max-h-36 min-h-14 flex-1 resize-none rounded-xl border border-zinc-300 bg-white px-4 py-2.5 text-base text-zinc-900 placeholder:text-zinc-400 focus:border-brand-500 focus:ring-3 focus:ring-brand-500/15 focus:outline-none sm:text-sm dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100" onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); event.currentTarget.form?.requestSubmit() } }} />
          <button type="submit" disabled={!body.trim() || send.isPending} className={buttonClasses('primary')}><Send className="h-4 w-4" aria-hidden="true" /><span className="hidden sm:inline">{send.isPending ? (english ? 'Sending…' : 'שולחים…') : (english ? 'Send' : 'שליחה')}</span></button>
        </div>
        {send.isError && <p role="alert" className="mx-auto mt-2 max-w-4xl text-sm text-danger-700">{send.error.message}</p>}
        {request.status === 'resolved' && <p className="mx-auto mt-2 max-w-4xl text-xs text-zinc-500">{english ? 'Sending a new message will reopen this request.' : 'שליחת הודעה חדשה תפתח את הפנייה מחדש.'}</p>}
      </form>
    </div>
  </div>, document.body)
}
