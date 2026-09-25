import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowDown, CheckCircle2, ChevronRight, Headset, SendHorizontal } from 'lucide-react'
import {
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
  type ReactNode,
  type RefObject,
} from 'react'
import { createPortal } from 'react-dom'
import { useTranslation } from 'react-i18next'

import { useDialogA11y } from '../hooks/useDialogA11y'
import { useNow } from '../hooks/useNow'
import {
  formatClockTime,
  formatDay,
  formatFullTimestamp,
  localDayKey,
  parseServerTimestamp,
} from '../lib/supportTime'
import {
  listSupportMessages,
  sendSupportMessage,
  type SupportMessage,
  type SupportRequest,
} from '../services/supportService'
import { SupportStatusBadge } from './support/SupportStatusBadge'
import { providerLabel } from '../lib/support'
import { buttonClasses, cx } from './ui-classes'

const NEAR_BOTTOM_PX = 96
const GROUP_WINDOW_MS = 5 * 60 * 1000
const COMPOSER_MAX_HEIGHT_PX = 160

/**
 * Keeps the full-screen conversation inside the *visible* viewport. On mobile
 * the on-screen keyboard shrinks the visual viewport but not the layout one,
 * which would otherwise hide the composer behind the keyboard.
 */
function useVisualViewportFit(ref: RefObject<HTMLElement | null>) {
  useEffect(() => {
    const viewport = window.visualViewport
    const element = ref.current
    if (!viewport || !element) return
    const update = () => {
      element.style.height = `${viewport.height}px`
      element.style.transform = viewport.offsetTop ? `translateY(${viewport.offsetTop}px)` : ''
    }
    update()
    viewport.addEventListener('resize', update)
    viewport.addEventListener('scroll', update)
    return () => {
      viewport.removeEventListener('resize', update)
      viewport.removeEventListener('scroll', update)
      element.style.height = ''
      element.style.transform = ''
    }
  }, [ref])
}

function AuthorMark({ message }: { message: SupportMessage }) {
  if (message.author_type === 'staff') {
    return (
      <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-brand-600 text-white dark:bg-brand-500 dark:text-brand-950" aria-hidden="true">
        <Headset className="h-3.5 w-3.5" />
      </span>
    )
  }
  const initial = (message.author_name?.trim() || '?').charAt(0).toLocaleUpperCase()
  return (
    <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-zinc-200 text-[11px] font-semibold text-zinc-700 dark:bg-zinc-700 dark:text-zinc-200" aria-hidden="true">
      {initial}
    </span>
  )
}

export function SupportConversationDialog({
  request,
  staff,
  onClose,
  actions,
}: {
  request: SupportRequest
  staff: boolean
  onClose: () => void
  actions?: ReactNode
}) {
  const { t, i18n } = useTranslation()
  const queryClient = useQueryClient()
  const now = useNow()
  const [body, setBody] = useState('')
  const [hasUnseen, setHasUnseen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)
  const dialogRef = useRef<HTMLDivElement>(null)
  const scrollerRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const pinnedRef = useRef(true)
  const lastRenderedIdRef = useRef<string | null>(null)
  const justSentRef = useRef(false)
  const titleId = useId()
  const contextId = useId()
  const hintId = useId()
  const replyId = useId()
  useDialogA11y({ dialogRef, isLoading: false, onClose })
  useVisualViewportFit(rootRef)

  const queryKey = ['support-messages', staff ? 'staff' : 'customer', request.id]
  const messages = useQuery({
    queryKey,
    queryFn: () => listSupportMessages(request.id, staff),
    refetchInterval: 3_000,
    refetchOnWindowFocus: 'always',
  })
  const send = useMutation({
    mutationFn: (message: string) => sendSupportMessage(request.id, message, staff),
    onSuccess: () => {
      setBody('')
      justSentRef.current = true
      void queryClient.invalidateQueries({ queryKey })
      void queryClient.invalidateQueries({ queryKey: [staff ? 'staff-requests' : 'support-requests-own'] })
    },
  })

  const isOwn = (message: SupportMessage) => (staff ? message.author_type === 'staff' : message.author_type === 'customer')
  // Customers never see individual staff names — only the team.
  const authorLabel = (message: SupportMessage) => {
    if (isOwn(message) && !staff) return t('support.conversation.you')
    if (message.author_type === 'staff') return staff ? message.author_name || t('support.conversation.team') : t('support.conversation.team')
    return message.author_name || t('support.conversation.customer')
  }

  useEffect(() => {
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = previousOverflow }
  }, [])

  // Focus moves into the dialog. Only pointer devices get the composer, so a phone keyboard doesn't pop up uninvited.
  useEffect(() => {
    if (window.matchMedia?.('(pointer: fine)').matches) textareaRef.current?.focus({ preventScroll: true })
    else dialogRef.current?.focus({ preventScroll: true })
  }, [])

  useLayoutEffect(() => {
    const element = textareaRef.current
    if (!element) return
    element.style.height = 'auto'
    element.style.height = `${Math.min(element.scrollHeight, COMPOSER_MAX_HEIGHT_PX)}px`
  }, [body])

  // Follow new messages only when the reader is already at the bottom (or just sent one).
  useLayoutEffect(() => {
    const list = messages.data
    const scroller = scrollerRef.current
    if (!list?.length || !scroller) return
    const lastId = list[list.length - 1].id
    if (lastRenderedIdRef.current === lastId) return
    const firstRender = lastRenderedIdRef.current === null
    lastRenderedIdRef.current = lastId
    if (firstRender || pinnedRef.current || justSentRef.current || isOwn(list[list.length - 1])) {
      scroller.scrollTop = scroller.scrollHeight
      setHasUnseen(false)
    } else {
      setHasUnseen(true)
    }
    justSentRef.current = false
    // isOwn only depends on `staff`, which never changes for a mounted dialog.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages.data])

  // Keep the latest message in view when the viewport shrinks (keyboard) or the composer grows.
  useEffect(() => {
    const scroller = scrollerRef.current
    if (!scroller || typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(() => {
      if (pinnedRef.current) scroller.scrollTop = scroller.scrollHeight
    })
    observer.observe(scroller)
    return () => observer.disconnect()
  }, [])

  function handleScroll() {
    const scroller = scrollerRef.current
    if (!scroller) return
    const atBottom = scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight < NEAR_BOTTOM_PX
    pinnedRef.current = atBottom
    if (atBottom) setHasUnseen(false)
  }

  function jumpToLatest() {
    const scroller = scrollerRef.current
    if (!scroller) return
    scroller.scrollTo({ top: scroller.scrollHeight, behavior: window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' })
    setHasUnseen(false)
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    const message = body.trim()
    if (message && !send.isPending) send.mutate(message)
  }

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      event.currentTarget.form?.requestSubmit()
    }
  }

  const created = parseServerTimestamp(request.created_at)
  const today = localDayKey(now)
  const yesterday = localDayKey(new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1))
  const dayLabel = (date: Date) => {
    const key = localDayKey(date)
    if (key === today) return t('support.conversation.today')
    if (key === yesterday) return t('support.conversation.yesterday')
    return formatDay(date, i18n.language, now)
  }

  return createPortal(
    <div ref={rootRef} className="fixed inset-x-0 top-0 z-50 flex h-[100dvh] w-full animate-fade-in flex-col overflow-hidden bg-zinc-50 dark:bg-zinc-950">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={contextId}
        tabIndex={-1}
        className="flex h-full min-h-0 flex-col overflow-hidden focus:outline-none"
      >
        <header className="shrink-0 border-b border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
          <div className="flex items-center gap-2 px-2 py-2 sm:gap-3 sm:px-4">
            <button
              type="button"
              onClick={onClose}
              aria-label={t('support.conversation.back')}
              className="inline-flex h-10 shrink-0 items-center gap-1.5 rounded-lg px-2.5 text-sm font-medium text-zinc-600 transition-colors hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800 dark:hover:text-zinc-50"
            >
              <ChevronRight className="h-5 w-5 ltr:rotate-180" aria-hidden="true" />
              <span className="hidden md:inline">{t('support.conversation.back')}</span>
            </button>
            <div className="min-w-0 flex-1">
              <div className="flex min-w-0 items-center gap-2">
                <h2 id={titleId} title={request.subject} dir="auto" className="min-w-0 truncate text-[0.9375rem] font-semibold text-zinc-900 dark:text-zinc-50">
                  {request.subject}
                </h2>
                <SupportStatusBadge status={request.status} />
              </div>
              <p id={contextId} className="mt-0.5 truncate text-xs text-zinc-500 dark:text-zinc-400">
                {staff ? (
                  <>
                    {request.business_name}
                    {request.requester_email && <> · <bdi dir="ltr">{request.requester_email}</bdi></>}
                  </>
                ) : (
                  <time dateTime={created.toISOString()}>{formatFullTimestamp(created, i18n.language)}</time>
                )}
                {request.provider && <> · {providerLabel(request.provider)}</>}
              </p>
            </div>
            {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
          </div>
        </header>

        <div className="relative min-h-0 flex-1">
          <div
            ref={scrollerRef}
            onScroll={handleScroll}
            className="h-full overflow-y-auto overscroll-contain px-3 py-5 sm:px-6 sm:py-8"
          >
            <div className="mx-auto w-full max-w-3xl">
              {messages.isPending && (
                <p role="status" className="py-10 text-center text-sm text-zinc-500 dark:text-zinc-400">{t('support.conversation.loading')}</p>
              )}
              {messages.isError && !messages.data && (
                <p role="alert" className="rounded-lg bg-danger-50 px-3 py-2 text-center text-sm text-danger-700 dark:bg-danger-500/10 dark:text-danger-500">
                  {t('support.conversation.loadError')}
                </p>
              )}
              <ol aria-label={t('support.conversation.messagesLabel')} className="flex flex-col">
                {messages.data?.map((message, index) => {
                  const sent = parseServerTimestamp(message.created_at)
                  const previous = index > 0 ? messages.data[index - 1] : null
                  const previousSent = previous ? parseServerTimestamp(previous.created_at) : null
                  const newDay = !previousSent || localDayKey(previousSent) !== localDayKey(sent)
                  const continued = !newDay && previous?.author_type === message.author_type
                    && sent.getTime() - (previousSent?.getTime() ?? 0) < GROUP_WINDOW_MS
                  const own = isOwn(message)
                  return (
                    <li key={message.id} className={cx('flex flex-col', own ? 'items-end' : 'items-start', continued ? 'mt-1' : 'mt-5 first:mt-0')}>
                      {newDay && (
                        <div className="mb-5 flex w-full items-center gap-3 text-xs font-medium text-zinc-500 dark:text-zinc-400" role="separator">
                          <span className="h-px flex-1 bg-zinc-200 dark:bg-zinc-800" aria-hidden="true" />
                          {dayLabel(sent)}
                          <span className="h-px flex-1 bg-zinc-200 dark:bg-zinc-800" aria-hidden="true" />
                        </div>
                      )}
                      {continued ? (
                        <span className="sr-only">{authorLabel(message)}, {formatClockTime(sent, i18n.language)}</span>
                      ) : (
                        <div className={cx('mb-1.5 flex items-center gap-2 px-0.5 text-xs', own && 'flex-row-reverse')}>
                          <AuthorMark message={message} />
                          <span className="font-medium text-zinc-700 dark:text-zinc-200">{authorLabel(message)}</span>
                          <time dateTime={sent.toISOString()} title={formatFullTimestamp(sent, i18n.language)} className="text-zinc-500 dark:text-zinc-400">
                            {formatClockTime(sent, i18n.language)}
                          </time>
                        </div>
                      )}
                      <p
                        dir="auto"
                        title={continued ? formatFullTimestamp(sent, i18n.language) : undefined}
                        className={cx(
                          'max-w-[min(88%,40rem)] rounded-2xl px-4 py-2.5 text-[0.9375rem] leading-relaxed whitespace-pre-wrap break-words ring-1 sm:text-sm',
                          own
                            ? 'bg-brand-50 text-zinc-900 ring-brand-100 dark:bg-brand-500/10 dark:text-zinc-100 dark:ring-brand-500/20'
                            : 'bg-white text-zinc-900 shadow-card ring-zinc-200 dark:bg-zinc-900 dark:text-zinc-100 dark:ring-zinc-800',
                        )}
                      >
                        {message.body}
                      </p>
                    </li>
                  )
                })}
              </ol>
            </div>
          </div>
          {hasUnseen && (
            <button
              type="button"
              onClick={jumpToLatest}
              className={buttonClasses('secondary', 'sm', 'absolute bottom-3 left-1/2 -translate-x-1/2 animate-pop-in rounded-full shadow-raised')}
            >
              <ArrowDown className="h-3.5 w-3.5" aria-hidden="true" />
              {t('support.conversation.newMessages')}
            </button>
          )}
        </div>

        <form
          onSubmit={submit}
          className="shrink-0 border-t border-zinc-200 bg-white px-3 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] sm:px-6 dark:border-zinc-800 dark:bg-zinc-900"
        >
          <div className="mx-auto max-w-3xl">
            {request.status === 'resolved' && (
              <p className="mb-2.5 flex items-start gap-2 rounded-lg bg-zinc-100 px-3 py-2 text-xs leading-relaxed text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
                <CheckCircle2 className="mt-px h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                {t('support.conversation.resolvedNotice')}
              </p>
            )}
            <div className="flex items-end gap-2 rounded-xl border border-zinc-300 bg-white p-1.5 transition-shadow focus-within:border-brand-500 focus-within:ring-3 focus-within:ring-brand-500/15 dark:border-zinc-700 dark:bg-zinc-950">
              <label htmlFor={replyId} className="sr-only">{t('support.conversation.replyLabel')}</label>
              <textarea
                ref={textareaRef}
                id={replyId}
                rows={1}
                maxLength={5000}
                value={body}
                onChange={(event) => setBody(event.target.value)}
                onKeyDown={handleComposerKeyDown}
                placeholder={t('support.conversation.placeholder')}
                aria-describedby={hintId}
                dir="auto"
                className="min-h-10 flex-1 resize-none bg-transparent px-2.5 py-2 text-base leading-6 text-zinc-900 placeholder:text-zinc-400 sm:text-sm dark:text-zinc-100 dark:placeholder:text-zinc-500"
                // The wrapper's focus-within ring is the focus indicator; the global outline rule is unlayered, so it's overridden inline.
                style={{ maxHeight: COMPOSER_MAX_HEIGHT_PX, outline: 'none' }}
              />
              <button
                type="submit"
                disabled={!body.trim() || send.isPending}
                aria-label={send.isPending ? t('support.conversation.sending') : t('support.conversation.send')}
                className={buttonClasses('primary', 'md', 'h-10 min-w-10 px-3 sm:px-4')}
              >
                <SendHorizontal className="h-4 w-4 rtl:-scale-x-100" aria-hidden="true" />
                <span className="hidden sm:inline">{send.isPending ? t('support.conversation.sending') : t('support.conversation.send')}</span>
              </button>
            </div>
            <p id={hintId} className="mt-1.5 hidden text-xs text-zinc-500 sm:block dark:text-zinc-400">{t('support.conversation.shortcut')}</p>
            {send.isError && (
              <p role="alert" className="mt-1.5 text-sm text-danger-700 dark:text-danger-500">
                {send.error.message || t('support.conversation.sendError')}
              </p>
            )}
          </div>
        </form>
      </div>
    </div>,
    document.body,
  )
}
