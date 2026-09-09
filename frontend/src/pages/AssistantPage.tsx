import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { sendChatMessage } from '../services/assistantService'
import type { ChatMessage } from '../types/assistant'

export function AssistantPage() {
  const { t } = useTranslation()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [isSending, setIsSending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const exampleQuestions = [
    t('assistant.exampleQuestion1'),
    t('assistant.exampleQuestion2'),
    t('assistant.exampleQuestion3'),
  ]

  async function send(question: string) {
    const trimmed = question.trim()
    if (!trimmed || isSending) return

    const history = messages
    const userMessage: ChatMessage = { role: 'user', content: trimmed }
    setMessages([...history, userMessage])
    setInput('')
    setError(null)
    setIsSending(true)
    try {
      const reply = await sendChatMessage(trimmed, history)
      setMessages([...history, userMessage, { role: 'assistant', content: reply }])
    } catch {
      // Always the translated, generic message — never the raw backend
      // detail text, which may be untranslated/technical (matches the
      // "never leak the raw provider error" rule the backend route itself
      // already follows for this endpoint).
      setError(t('assistant.errorMessage'))
    } finally {
      setIsSending(false)
    }
  }

  return (
    <div className="mx-auto flex h-[70vh] max-w-2xl flex-col">
      <div>
        <h1 className="text-2xl font-semibold text-stone-900 dark:text-stone-100">{t('assistant.title')}</h1>
        <p className="mt-1 text-sm text-stone-500 dark:text-stone-400">{t('assistant.subtitle')}</p>
      </div>

      <div className="mt-6 flex-1 space-y-3 overflow-y-auto rounded-2xl border border-stone-200 bg-white p-4 shadow-sm dark:border-stone-800 dark:bg-stone-900">
        {messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
            <p className="text-sm font-medium text-stone-700 dark:text-stone-300">{t('assistant.emptyTitle')}</p>
            <div className="flex flex-wrap justify-center gap-2">
              {exampleQuestions.map((question) => (
                <button
                  key={question}
                  type="button"
                  onClick={() => send(question)}
                  className="rounded-full border border-stone-300 px-3 py-1.5 text-sm text-stone-700 hover:bg-stone-50 dark:border-stone-700 dark:text-stone-300 dark:hover:bg-stone-800"
                >
                  {question}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg, index) => (
            <div key={index} className={msg.role === 'user' ? 'flex justify-end' : 'flex justify-start'}>
              <p
                className={
                  msg.role === 'user'
                    ? 'max-w-[80%] rounded-lg bg-brand-600 px-3 py-2 text-sm text-white'
                    : 'max-w-[80%] rounded-lg bg-stone-100 px-3 py-2 text-sm text-stone-900 dark:bg-stone-800 dark:text-stone-100'
                }
              >
                {msg.content}
              </p>
            </div>
          ))
        )}
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
          className="flex-1 rounded-lg border border-stone-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none dark:border-stone-700 dark:bg-stone-800 dark:text-stone-100"
        />
        <button
          type="submit"
          disabled={isSending}
          className="rounded-md bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
        >
          {t('assistant.send')}
        </button>
      </form>
    </div>
  )
}
