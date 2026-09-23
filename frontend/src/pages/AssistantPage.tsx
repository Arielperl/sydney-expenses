import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { MessageSquare, Pencil, Plus, Trash2 } from 'lucide-react'
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

  const isInitialLoading = conversationsQuery.isLoading ||
    (typeof activeConversationId === 'string' && conversationQuery.isLoading && messages.length === 0)

  return (
    <div className="flex h-[76vh] min-h-[560px] flex-col">
      <div>
        <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100">{t('assistant.title')}</h1>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">{t('assistant.subtitle')}</p>
      </div>

      <div className="mt-5 grid min-h-0 flex-1 gap-4 lg:grid-cols-[300px_minmax(0,1fr)]">
        <aside className="flex min-h-0 flex-col rounded-2xl border border-zinc-200 bg-white p-3 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
          <button
            type="button"
            onClick={startNewConversation}
            className="flex items-center justify-center gap-2 rounded-xl bg-brand-600 px-3 py-2.5 text-sm font-semibold text-white hover:bg-brand-700"
          >
            <Plus size={17} />
            {t('assistant.newConversation')}
          </button>
          <p className="mb-2 mt-4 px-2 text-xs font-semibold uppercase tracking-wide text-zinc-400">
            {t('assistant.conversations')}
          </p>
          <div className="flex gap-2 overflow-x-auto lg:flex-1 lg:flex-col lg:overflow-y-auto">
            {(conversationsQuery.data ?? []).map((conversation) => (
              <div
                key={conversation.id}
                className={`group flex min-w-[280px] items-start gap-1 rounded-xl lg:min-w-0 ${
                  activeConversationId === conversation.id
                    ? 'bg-brand-50 text-brand-800 dark:bg-brand-950/40 dark:text-brand-200'
                    : 'text-zinc-600 hover:bg-zinc-50 dark:text-zinc-300 dark:hover:bg-zinc-800'
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
                    className="shrink-0 rounded-lg p-1.5 text-zinc-400 hover:bg-white hover:text-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-1 dark:hover:bg-zinc-700"
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
                    className="shrink-0 rounded-lg p-1.5 text-zinc-400 hover:bg-white hover:text-danger-600 focus:outline-none focus:ring-2 focus:ring-danger-500 focus:ring-offset-1 dark:hover:bg-zinc-700"
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              </div>
            ))}
            {conversationsQuery.data?.length === 0 && (
              <p className="px-2 py-3 text-sm text-zinc-400">{t('assistant.noConversations')}</p>
            )}
          </div>
        </aside>

        <section className="flex min-h-0 flex-col">
          <div className="flex-1 space-y-3 overflow-y-auto rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
            {isInitialLoading ? (
              <div className="flex h-full items-center justify-center text-sm text-zinc-400">
                {t('assistant.loadingConversation')}
              </div>
            ) : messages.length === 0 ? (
              <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
                <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300">{t('assistant.emptyTitle')}</p>
                <div className="flex flex-wrap justify-center gap-2">
                  {exampleQuestions.map((question) => (
                    <button
                      key={question}
                      type="button"
                      onClick={() => send(question)}
                      className="rounded-full border border-zinc-300 px-3 py-1.5 text-sm text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
                    >
                      {question}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((message, index) => (
                <div key={message.id ?? index} className={message.role === 'user' ? 'flex justify-end' : 'flex justify-start'}>
                  <p
                    className={
                      message.role === 'user'
                        ? 'max-w-[80%] whitespace-pre-wrap rounded-lg bg-brand-600 px-3 py-2 text-sm text-white'
                        : 'max-w-[80%] whitespace-pre-wrap rounded-lg bg-zinc-100 px-3 py-2 text-sm text-zinc-900 dark:bg-zinc-800 dark:text-zinc-100'
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
                  className="flex items-center gap-1 rounded-lg bg-zinc-100 px-3 py-2.5 dark:bg-zinc-800"
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
            {error && <p className="text-sm text-danger-700 dark:text-danger-400">{error}</p>}
          </div>

          <form
            className="mt-4 flex gap-2"
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
              className="flex-1 rounded-lg border border-zinc-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
            />
            <button
              type="submit"
              disabled={sendMutation.isPending}
              className="rounded-md bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
            >
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
