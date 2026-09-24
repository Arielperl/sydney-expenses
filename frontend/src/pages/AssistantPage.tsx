import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { MessageSquare, Pencil, Plus, Trash2, Bot, SendHorizontal } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { ConfirmDialog } from '../components/ConfirmDialog'
import { RenameConversationDialog } from '../components/RenameConversationDialog'
import {
  deleteAssistantConversation,
  getAssistantConversation,
  listAssistantConversations,
  renameAssistantConversation,
  sendChatMessage,
} from '../services/assistantService'
import type { AssistantConversation, AssistantConversationDetail, ChatMessage } from '../types/assistant'
import { buttonClasses, cardClasses, cx } from '../components/ui-classes'
import { PageHeader } from '../components/ui'
import { inputClasses } from '../components/FormField'

export function AssistantPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  // undefined means initial selection has not happened; null means the user
  // deliberately opened a fresh conversation.
  const [conversationId, setConversationId] = useState<string | null | undefined>(undefined)
  const [optimisticMessages, setOptimisticMessages] = useState<ChatMessage[] | null>(null)
  const [input, setInput] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [deletingConversationId, setDeletingConversationId] = useState<string | null>(null)
  const [renamingConversation, setRenamingConversation] = useState<{ id: string; title: string } | null>(null)
  const endRef = useRef<HTMLDivElement>(null)

  const conversationsQuery = useQuery({
    queryKey: ['assistant-conversations'],
    queryFn: listAssistantConversations,
  })
  const activeConversationId = conversationId === undefined
    ? conversationsQuery.data?.[0]?.id ?? null
    : conversationId
  const conversationQuery = useQuery({
    queryKey: ['assistant-conversation', activeConversationId],
    queryFn: () => getAssistantConversation(activeConversationId as string),
    enabled: typeof activeConversationId === 'string',
  })
  const messages = optimisticMessages ?? conversationQuery.data?.messages ?? []
  const messageCount = messages.length

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ behavior: 'smooth', block: 'nearest' })
  }, [messageCount])

  const sendMutation = useMutation({
    mutationFn: ({ question, activeId }: { question: string; activeId: string | null }) =>
      sendChatMessage(question, activeId),
  })
  const deleteMutation = useMutation({ mutationFn: deleteAssistantConversation })
  const renameMutation = useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) => renameAssistantConversation(id, title),
  })

  const exampleQuestions = [
    t('assistant.exampleQuestion1'),
    t('assistant.exampleQuestion2'),
    t('assistant.exampleQuestion3'),
  ]

  function startNewConversation() {
    if (sendMutation.isPending) return
    setConversationId(null)
    setOptimisticMessages([])
    setInput('')
    setError(null)
  }

  function requestDeleteConversation(id: string) {
    deleteMutation.reset()
    setDeletingConversationId(id)
  }

  function closeDeleteDialog() {
    if (deleteMutation.isPending) return
    setDeletingConversationId(null)
  }

  async function confirmDeleteConversation() {
    if (!deletingConversationId || deleteMutation.isPending) return
    const id = deletingConversationId
    try {
      await deleteMutation.mutateAsync(id)
      queryClient.removeQueries({ queryKey: ['assistant-conversation', id] })
      const remaining = (conversationsQuery.data ?? []).filter((conversation) => conversation.id !== id)
      queryClient.setQueryData(['assistant-conversations'], remaining)
      if (activeConversationId === id) {
        setConversationId(null)
        setOptimisticMessages([])
        setInput('')
        setError(null)
      }
      setDeletingConversationId(null)
    } catch {
      // Keep the dialog open — ConfirmDialog shows deleteMutation's error and lets the user retry or cancel.
    }
  }

  function requestRenameConversation(id: string, title: string) {
    renameMutation.reset()
    setRenamingConversation({ id, title })
  }

  function closeRenameDialog() {
    if (renameMutation.isPending) return
    setRenamingConversation(null)
  }

  async function saveRenamedConversation(newTitle: string) {
    if (!renamingConversation || renameMutation.isPending) return
    const { id } = renamingConversation
    try {
      const updated = await renameMutation.mutateAsync({ id, title: newTitle })
      queryClient.setQueryData<AssistantConversation[]>(['assistant-conversations'], (existing) =>
        (existing ?? []).map((conversation) =>
          conversation.id === id ? { ...conversation, title: updated.title, updated_at: updated.updated_at } : conversation,
        ),
      )
      queryClient.setQueryData<AssistantConversationDetail | undefined>(['assistant-conversation', id], (existing) =>
        existing ? { ...existing, title: updated.title, updated_at: updated.updated_at } : existing,
      )
      setRenamingConversation(null)
    } catch {
      // Keep the dialog open — RenameConversationDialog shows renameMutation's error and lets the user retry or cancel.
    }
  }

  async function send(question: string) {
    const trimmed = question.trim()
    if (!trimmed || sendMutation.isPending) return

    const activeId = activeConversationId ?? null
    const userMessage: ChatMessage = { role: 'user', content: trimmed }
    setOptimisticMessages([...messages, userMessage])
    setInput('')
    setError(null)
    try {
      const result = await sendMutation.mutateAsync({ question: trimmed, activeId })
      setOptimisticMessages([...messages, userMessage, { role: 'assistant', content: result.reply }])
      setConversationId(result.conversation_id)
      await queryClient.invalidateQueries({ queryKey: ['assistant-conversations'] })
      await queryClient.invalidateQueries({ queryKey: ['assistant-conversation', result.conversation_id] })
    } catch {
      // Remove the optimistic user bubble because the server persists a turn
      // only after the provider returns successfully.
      setOptimisticMessages(messages)
      setError(t('assistant.errorMessage'))
    }
  }

  const isInitialLoading = conversationsQuery.isPending ||
    (typeof activeConversationId === 'string' && conversationQuery.isPending && messages.length === 0)

  return (
    <div className="flex h-[calc(100dvh-9rem)] min-h-[560px] flex-col lg:h-[calc(100dvh-5rem)]">
      <PageHeader title={t('assistant.title')} description={t('assistant.subtitle')} />

      <div className="mt-6 grid min-h-0 flex-1 gap-4 lg:grid-cols-[280px_minmax(0,1fr)]">
        <aside className="flex min-h-0 flex-col rounded-xl border border-zinc-200/80 bg-white p-3 shadow-card max-lg:max-h-40 dark:border-zinc-800 dark:bg-zinc-900">
          <button
            type="button"
            onClick={startNewConversation}
            className={buttonClasses('primary', 'md', 'w-full')}
          >
            <Plus size={17} />
            {t('assistant.newConversation')}
          </button>
          <p className="mt-4 mb-2 px-2 text-xs font-medium text-zinc-500 dark:text-zinc-400">
            {t('assistant.conversations')}
          </p>
          <div className="flex gap-2 overflow-x-auto lg:flex-1 lg:flex-col lg:overflow-y-auto">
            {(conversationsQuery.data ?? []).map((conversation) => (
              <div
                key={conversation.id}
                className={`group flex min-w-[280px] items-start gap-1 rounded-xl lg:min-w-0 ${
                  activeConversationId === conversation.id
                    ? 'bg-brand-50 text-brand-800 dark:bg-brand-500/10 dark:text-brand-200'
                    : 'text-zinc-700 hover:bg-zinc-50 dark:text-zinc-300 dark:hover:bg-zinc-800/70'
                }`}
              >
                <button
                  type="button"
                  title={conversation.title}
                  onClick={() => {
                    setConversationId(conversation.id)
                    setOptimisticMessages(null)
                    setError(null)
                  }}
                  className="flex min-w-0 flex-1 items-start gap-2 px-2 py-2 text-start text-sm"
                >
                  <MessageSquare size={16} className="mt-0.5 shrink-0" />
                  <span className="line-clamp-2 break-words">{conversation.title}</span>
                </button>
                <div className="flex shrink-0 items-center gap-0.5 pt-1">
                  <button
                    type="button"
                    onClick={(event) => {
                      // Focus the trigger explicitly — clicking a button doesn't
                      // reliably focus it in every browser, and the dialog
                      // restores focus to whatever had it when it opened.
                      event.currentTarget.focus()
                      requestRenameConversation(conversation.id, conversation.title)
                    }}
                    aria-label={`${t('assistant.renameConversation')}: ${conversation.title}`}
                    title={t('assistant.renameConversation')}
                    className="shrink-0 rounded-md p-1.5 text-zinc-500 hover:bg-white hover:text-brand-700 dark:text-zinc-400 dark:hover:bg-zinc-700 dark:hover:text-brand-300"
                  >
                    <Pencil size={15} />
                  </button>
                  <button
                    type="button"
                    onClick={(event) => {
                      // Focus the trigger explicitly — clicking a button doesn't
                      // reliably focus it in every browser, and ConfirmDialog
                      // restores focus to whatever had it when it opened.
                      event.currentTarget.focus()
                      requestDeleteConversation(conversation.id)
                    }}
                    aria-label={`${t('assistant.deleteConversation')}: ${conversation.title}`}
                    title={t('assistant.deleteConversation')}
                    className="shrink-0 rounded-md p-1.5 text-zinc-500 hover:bg-white hover:text-danger-700 dark:text-zinc-400 dark:hover:bg-zinc-700 dark:hover:text-danger-500"
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              </div>
            ))}
            {conversationsQuery.data?.length === 0 && (
              <p className="px-2 py-3 text-sm text-zinc-500 dark:text-zinc-400">{t('assistant.noConversations')}</p>
            )}
          </div>
        </aside>

        <section className={cx(cardClasses, 'flex min-h-0 flex-col overflow-hidden')}>
          <div className="flex-1 space-y-4 overflow-y-auto p-4 sm:p-6" aria-live="polite">
            {isInitialLoading ? (
              <div className="flex h-full items-center justify-center text-sm text-zinc-500 dark:text-zinc-400">
                {t('assistant.loadingConversation')}
              </div>
            ) : messages.length === 0 ? (
              <div className="flex h-full flex-col items-center justify-center gap-4 px-4 text-center">
                <span className="grid h-12 w-12 place-items-center rounded-full bg-brand-50 text-brand-700 ring-1 ring-brand-100 dark:bg-brand-500/10 dark:text-brand-300 dark:ring-brand-500/20" aria-hidden="true">
                  <Bot className="h-5 w-5" />
                </span>
                <p className="text-[0.9375rem] font-medium text-zinc-900 dark:text-zinc-100">{t('assistant.emptyTitle')}</p>
                <div className="flex max-w-xl flex-wrap justify-center gap-2">
                  {exampleQuestions.map((question) => (
                    <button
                      key={question}
                      type="button"
                      onClick={() => send(question)}
                      className="rounded-full border border-zinc-200 bg-white px-3.5 py-1.5 text-sm text-zinc-700 shadow-card transition-colors hover:border-brand-300 hover:bg-brand-50/50 hover:text-brand-800 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:border-brand-500/40 dark:hover:bg-brand-500/10 dark:hover:text-brand-200"
                    >
                      {question}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((message, index) => (
                <div key={message.id ?? index} className={cx('flex animate-pop-in items-end gap-2', message.role === 'user' ? 'justify-end' : 'justify-start')}>
                  {message.role !== 'user' && (
                    <span className="mb-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-full bg-brand-50 text-brand-700 ring-1 ring-brand-100 dark:bg-brand-500/10 dark:text-brand-300 dark:ring-brand-500/20" aria-hidden="true">
                      <Bot className="h-3.5 w-3.5" />
                    </span>
                  )}
                  <p
                    dir="auto"
                    className={
                      message.role === 'user'
                        ? 'max-w-[80%] rounded-2xl rounded-ee-md bg-brand-600 px-3.5 py-2.5 text-sm leading-relaxed whitespace-pre-wrap text-white dark:bg-brand-500 dark:text-brand-950'
                        : 'max-w-[80%] rounded-2xl rounded-es-md bg-zinc-100 px-3.5 py-2.5 text-sm leading-relaxed whitespace-pre-wrap text-zinc-900 dark:bg-zinc-800 dark:text-zinc-100'
                    }
                  >
                    {message.content}
                  </p>
                </div>
              ))
            )}
            {sendMutation.isPending && (
              <div className="flex justify-start">
                <div
                  role="status"
                  aria-label={t('assistant.thinking')}
                  className="ms-9 flex items-center gap-1 rounded-2xl rounded-es-md bg-zinc-100 px-3.5 py-3 dark:bg-zinc-800"
                >
                  {[0, 150, 300].map((delay) => (
                    <span
                      key={delay}
                      className="h-1.5 w-1.5 animate-bounce rounded-full bg-zinc-400 dark:bg-zinc-500"
                      style={{ animationDelay: `${delay}ms` }}
                    />
                  ))}
                </div>
              </div>
            )}
            <div ref={endRef} />
            {error && <p role="alert" className="rounded-lg bg-danger-50 px-3 py-2 text-sm text-danger-700 dark:bg-danger-500/10 dark:text-danger-500">{error}</p>}
          </div>

          <form
            className="flex gap-2 border-t border-zinc-100 bg-zinc-50/60 p-3 dark:border-zinc-800 dark:bg-zinc-950/30"
            onSubmit={(event) => {
              event.preventDefault()
              send(input)
            }}
          >
            <input
              type="text"
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder={t('assistant.inputPlaceholder')}
              aria-label={t('assistant.inputPlaceholder')}
              dir="auto"
              className={`${inputClasses} flex-1`}
            />
            <button
              type="submit"
              disabled={sendMutation.isPending}
              className={buttonClasses('primary')}
            >
              <SendHorizontal className="h-4 w-4 rtl:-scale-x-100" aria-hidden="true" />
              {t('assistant.send')}
            </button>
          </form>
        </section>
      </div>

      {deletingConversationId && (
        <ConfirmDialog
          title={t('assistant.deleteConversation')}
          description={t('assistant.deleteConfirm')}
          confirmLabel={t('assistant.deleteConversationConfirmButton')}
          isLoading={deleteMutation.isPending}
          error={deleteMutation.isError ? t('assistant.deleteError') : null}
          onClose={closeDeleteDialog}
          onConfirm={confirmDeleteConversation}
        />
      )}

      {renamingConversation && (
        <RenameConversationDialog
          currentTitle={renamingConversation.title}
          isLoading={renameMutation.isPending}
          error={renameMutation.isError ? t('assistant.renameError') : null}
          onClose={closeRenameDialog}
          onSave={saveRenamedConversation}
        />
      )}
    </div>
  )
}
