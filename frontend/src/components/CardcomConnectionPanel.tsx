import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { useAuth } from '../contexts/AuthContext'
import { formatDateTime } from '../lib/format'
import { toApiError } from '../services/apiClient'
import {
  createConnection,
  deleteConnection,
  listConnectionEvents,
  listConnections,
  reprocessConnectionEvent,
  rotateConnectionUrl,
  setConnectionEnabled,
} from '../services/connectionService'
import type { Connection, WebhookEventRead } from '../types/connections'
import { Modal } from './Modal'

// Both provider panels share this list and invalidate it after changes.
const CONNECTIONS_QUERY_KEY = ['connections']

function absoluteWebhookUrl(webhookPath: string): string {
  return `${window.location.origin}${webhookPath}`
}

function StatusBadge({ connection }: { connection: Connection }) {
  const { t } = useTranslation()
  if (!connection.enabled) {
    return (
      <span className="inline-flex items-center rounded-full bg-zinc-100 px-2.5 py-0.5 text-xs font-medium text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400">
        {t('imports.cardcom.statusDisabled')}
      </span>
    )
  }
  if (connection.event_counts.processed === 0) {
    return (
      <span className="inline-flex items-center rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-700 dark:bg-amber-500/10 dark:text-amber-400">
        {t('imports.cardcom.statusWaiting')}
      </span>
    )
  }
  return (
    <span className="inline-flex items-center rounded-full bg-success-50 px-2.5 py-0.5 text-xs font-medium text-success-700 dark:bg-success-500/10 dark:text-success-400">
      {t('imports.cardcom.statusActive')}
    </span>
  )
}

function EventRow({ connectionId, event }: { connectionId: string; event: WebhookEventRead }) {
  const { t, i18n } = useTranslation()
  const queryClient = useQueryClient()
  const [error, setError] = useState<string | null>(null)
  const reprocess = useMutation({
    mutationFn: () => reprocessConnectionEvent(connectionId, event.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: CONNECTIONS_QUERY_KEY })
      queryClient.invalidateQueries({ queryKey: ['connection-events', connectionId] })
    },
    onError: (err) => setError(toApiError(err).message),
  })

  const statusStyles: Record<WebhookEventRead['status'], string> = {
    processed: 'text-success-700 dark:text-success-400',
    duplicate: 'text-zinc-500 dark:text-zinc-400',
    received: 'text-amber-700 dark:text-amber-400',
    failed: 'text-danger-700 dark:text-danger-400',
    rejected: 'text-danger-700 dark:text-danger-400',
  }

  return (
    <li className="flex flex-col gap-1 border-b border-zinc-100 py-2 text-sm last:border-0 dark:border-zinc-800">
      <div className="flex items-center justify-between gap-2">
        <span className={`font-medium ${statusStyles[event.status]}`}>{t(`imports.cardcom.eventStatus.${event.status}`)}</span>
        <span className="text-xs text-zinc-400 dark:text-zinc-500">{formatDateTime(event.received_at, i18n.language)}</span>
      </div>
      {event.failure_message && (
        <p className="text-xs text-zinc-500 dark:text-zinc-400">{event.failure_message}</p>
      )}
      {event.can_reprocess && (
        <div>
          <button
            type="button"
            onClick={() => reprocess.mutate()}
            disabled={reprocess.isPending}
            className="text-xs font-medium text-brand-600 hover:text-brand-700 disabled:opacity-50 dark:text-brand-400"
          >
            {reprocess.isPending ? t('imports.cardcom.reprocessing') : t('imports.cardcom.reprocess')}
          </button>
          {error && <p className="mt-1 text-xs text-danger-600 dark:text-danger-400">{error}</p>}
        </div>
      )}
    </li>
  )
}

function ConnectionActivity({ connectionId }: { connectionId: string }) {
  const { t } = useTranslation()
  const { data, isLoading } = useQuery({
    queryKey: ['connection-events', connectionId],
    queryFn: () => listConnectionEvents(connectionId),
  })

  if (isLoading) return <p className="mt-3 text-xs text-zinc-400 dark:text-zinc-500">{t('common.loading')}</p>
  if (!data) return null

  return (
    <div className="mt-3 rounded-lg border border-zinc-200 bg-zinc-50 p-3 dark:border-zinc-800 dark:bg-zinc-800/40">
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-zinc-500 dark:text-zinc-400">
        <span>{t('imports.cardcom.countsProcessed', { count: data.counts.processed })}</span>
        <span>{t('imports.cardcom.countsDuplicate', { count: data.counts.duplicate })}</span>
        <span>{t('imports.cardcom.countsFailed', { count: data.counts.failed })}</span>
        <span>{t('imports.cardcom.countsRejected', { count: data.counts.rejected })}</span>
      </div>
      {data.events.length === 0 ? (
        <p className="mt-2 text-xs text-zinc-400 dark:text-zinc-500">{t('imports.cardcom.noActivityYet')}</p>
      ) : (
        <ul className="mt-2">
          {data.events.map((event) => (
            <EventRow key={event.id} connectionId={connectionId} event={event} />
          ))}
        </ul>
      )}
    </div>
  )
}

function ConnectionCard({ connection, startExpanded = false }: { connection: Connection; startExpanded?: boolean }) {
  const { t, i18n } = useTranslation()
  const { user } = useAuth()
  const isOwner = user?.role === 'owner'
  const queryClient = useQueryClient()
  const [copied, setCopied] = useState(false)
  const [showDetails, setShowDetails] = useState(startExpanded)
  const [showActivity, setShowActivity] = useState(false)
  const [confirmingRotate, setConfirmingRotate] = useState(false)
  const [confirmingDelete, setConfirmingDelete] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  const invalidate = () => queryClient.invalidateQueries({ queryKey: CONNECTIONS_QUERY_KEY })

  const toggleEnabled = useMutation({
    mutationFn: () => setConnectionEnabled(connection.id, !connection.enabled),
    onSuccess: invalidate,
    onError: (err) => setActionError(toApiError(err).message),
  })
  const rotate = useMutation({
    mutationFn: () => rotateConnectionUrl(connection.id),
    onSuccess: () => {
      invalidate()
      setConfirmingRotate(false)
    },
    onError: (err) => setActionError(toApiError(err).message),
  })
  const remove = useMutation({
    mutationFn: () => deleteConnection(connection.id),
    onSuccess: invalidate,
    onError: (err) => setActionError(toApiError(err).message),
  })

  function handleCopy() {
    void navigator.clipboard.writeText(absoluteWebhookUrl(connection.webhook_path)).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <div className="rounded-xl border border-zinc-200 p-4 dark:border-zinc-800">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <p className="font-medium text-zinc-900 dark:text-zinc-100">{connection.name}</p>
          <span className="rounded-full bg-brand-50 px-2 py-0.5 text-xs font-medium text-brand-700 dark:bg-brand-500/10 dark:text-brand-400">
            Cardcom
          </span>
          {connection.cardcom_terminal_number && (
            <span className="text-xs text-zinc-400 dark:text-zinc-500">
              {t('imports.cardcom.terminalLabel', { number: connection.cardcom_terminal_number })}
            </span>
          )}
        </div>
        <StatusBadge connection={connection} />
      </div>

      <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
        {connection.last_event_at
          ? t('imports.cardcom.lastEventAt', { time: formatDateTime(connection.last_event_at, i18n.language) })
          : t('imports.cardcom.noEventsYet')}
      </p>

      {connection.event_counts.failed > 0 && (
        <p className="mt-2 text-xs font-medium text-danger-700 dark:text-danger-400">{t('imports.eventsNeedAttention', { count: connection.event_counts.failed })}</p>
      )}
      <button type="button" onClick={() => setShowDetails((value) => !value)} aria-expanded={showDetails} className="mt-3 text-sm font-medium text-brand-700 hover:underline dark:text-brand-400">
        {showDetails ? t('imports.hideConnectionDetails') : connection.event_counts.processed === 0 ? t('imports.continueSetup') : t('imports.showConnectionDetails')}
      </button>

      {showDetails && <div className="mt-3 border-t border-zinc-100 pt-3 dark:border-zinc-800">
        {connection.enabled && connection.event_counts.processed === 0 && <p className="mb-3 text-sm text-zinc-600 dark:text-zinc-400">{t('imports.cardcom.howTo')}</p>}
        <p className="mb-2 text-xs font-medium text-zinc-600 dark:text-zinc-400">{t('imports.webhookAddress')}</p>
        <div className="flex items-center gap-2 rounded-lg bg-zinc-50 p-2 dark:bg-zinc-800/60">
          <code dir="ltr" className="flex-1 truncate text-xs text-zinc-700 dark:text-zinc-300">
            {absoluteWebhookUrl(connection.webhook_path)}
          </code>
          <button
            type="button"
            onClick={handleCopy}
            className="shrink-0 rounded-md border border-zinc-300 px-2.5 py-1 text-xs font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-700"
          >
            {copied ? t('imports.cardcom.copied') : t('imports.cardcom.copyUrl')}
          </button>
        </div>

        {isOwner && (
          <details className="mt-3 rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
            <summary className="cursor-pointer text-xs font-medium text-zinc-600 dark:text-zinc-400">{t('imports.advancedManagement')}</summary>
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => toggleEnabled.mutate()}
                disabled={toggleEnabled.isPending}
                className="rounded-md border border-zinc-300 px-3 py-1.5 text-xs font-medium text-zinc-700 hover:bg-zinc-50 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800"
              >
                {connection.enabled ? t('imports.cardcom.disable') : t('imports.cardcom.enable')}
              </button>
              <button
                type="button"
                onClick={() => setConfirmingRotate(true)}
                className="rounded-md border border-amber-400/50 px-3 py-1.5 text-xs font-medium text-amber-700 hover:bg-amber-50 dark:border-amber-500/40 dark:text-amber-400 dark:hover:bg-amber-500/10"
              >
                {t('imports.cardcom.rotateUrl')}
              </button>
              <button
                type="button"
                onClick={() => setConfirmingDelete(true)}
                className="rounded-md border border-danger-400/50 px-3 py-1.5 text-xs font-medium text-danger-700 hover:bg-danger-50 dark:border-danger-500/40 dark:text-danger-400 dark:hover:bg-danger-500/10"
              >
                {t('imports.cardcom.delete')}
              </button>
            </div>
          </details>
        )}

        <button type="button" onClick={() => setShowActivity((value) => !value)} className="mt-3 text-xs font-medium text-brand-600 hover:text-brand-700 dark:text-brand-400">
          {showActivity ? t('imports.cardcom.hideActivity') : t('imports.cardcom.showActivity')}
        </button>

        {actionError && <p className="mt-2 text-xs text-danger-600 dark:text-danger-400">{actionError}</p>}

        {showActivity && <ConnectionActivity connectionId={connection.id} />}
        <details className="mt-3 text-xs text-zinc-500 dark:text-zinc-400">
          <summary className="cursor-pointer font-medium">{t('imports.importantNotes')}</summary>
          <div className="mt-2 space-y-2">
            <p>{t('imports.cardcom.refundsNote')}</p>
            <p>{t('imports.cardcom.declinedNote')}</p>
            <p>{t('imports.cardcom.csvFallbackNote')}</p>
          </div>
        </details>
      </div>}

      {confirmingRotate && (
        <Modal title={t('imports.cardcom.rotateUrlTitle')} onClose={() => setConfirmingRotate(false)}>
          <p className="text-sm text-zinc-600 dark:text-zinc-400">{t('imports.cardcom.rotateUrlWarning')}</p>
          {actionError && <p className="mt-2 text-sm text-danger-600 dark:text-danger-400">{actionError}</p>}
          <div className="mt-4 flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setConfirmingRotate(false)}
              className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800"
            >
              {t('common.cancel')}
            </button>
            <button
              type="button"
              disabled={rotate.isPending}
              onClick={() => rotate.mutate()}
              className="rounded-md bg-amber-600 px-4 py-2 text-sm font-semibold text-white hover:bg-amber-700 disabled:opacity-60"
            >
              {rotate.isPending ? t('common.saving') : t('imports.cardcom.confirmRotate')}
            </button>
          </div>
        </Modal>
      )}

      {confirmingDelete && (
        <Modal title={t('imports.cardcom.deleteTitle')} onClose={() => setConfirmingDelete(false)}>
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            {t('imports.cardcom.deleteWarning', { name: connection.name })}
          </p>
          {actionError && <p className="mt-2 text-sm text-danger-600 dark:text-danger-400">{actionError}</p>}
          <div className="mt-4 flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setConfirmingDelete(false)}
              className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800"
            >
              {t('common.cancel')}
            </button>
            <button
              type="button"
              disabled={remove.isPending}
              onClick={() => remove.mutate()}
              className="rounded-md bg-danger-600 px-4 py-2 text-sm font-semibold text-white hover:bg-danger-700 disabled:opacity-60"
            >
              {remove.isPending ? t('common.deleting') : t('imports.cardcom.confirmDelete')}
            </button>
          </div>
        </Modal>
      )}
    </div>
  )
}

function CreateConnectionForm({ onCreated }: { onCreated: (id: string) => void }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [terminalNumber, setTerminalNumber] = useState('')
  const [apiName, setApiName] = useState('')
  const [apiPassword, setApiPassword] = useState('')
  const [error, setError] = useState<string | null>(null)

  const isValid = name.trim().length >= 2 && terminalNumber.trim().length > 0 && apiName.trim().length > 0

  const create = useMutation({
    mutationFn: () =>
      createConnection(name.trim(), 'cardcom', {
        terminalNumber: terminalNumber.trim(),
        apiName: apiName.trim(),
        apiPassword: apiPassword.trim() || undefined,
      }),
    onSuccess: (connection) => {
      setName('')
      setTerminalNumber('')
      setApiName('')
      setApiPassword('')
      setError(null)
      onCreated(connection.id)
      queryClient.invalidateQueries({ queryKey: CONNECTIONS_QUERY_KEY })
    },
    onError: (err) => setError(toApiError(err).message),
  })

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault()
        if (isValid) create.mutate()
      }}
      className="mt-4 space-y-2 rounded-lg border border-zinc-200 p-3 dark:border-zinc-800"
    >
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        <label className="text-xs font-medium text-zinc-700 dark:text-zinc-300">
          {t('imports.connectionName')}
          <input
            type="text" value={name} onChange={(event) => setName(event.target.value)}
            placeholder={t('imports.cardcom.newConnectionPlaceholder')}
            className="mt-1 block w-full min-w-0 rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
          />
        </label>
        <label className="text-xs font-medium text-zinc-700 dark:text-zinc-300">
          {t('imports.cardcom.terminalNumberPlaceholder')}
          <input
            type="text" value={terminalNumber} onChange={(event) => setTerminalNumber(event.target.value)}
            placeholder={t('imports.cardcom.terminalNumberPlaceholder')} dir="ltr"
            className="mt-1 block w-full min-w-0 rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
          />
        </label>
        <label className="text-xs font-medium text-zinc-700 dark:text-zinc-300">
          {t('imports.cardcom.apiNamePlaceholder')}
          <input
            type="text" value={apiName} onChange={(event) => setApiName(event.target.value)}
            placeholder={t('imports.cardcom.apiNamePlaceholder')} dir="ltr" autoComplete="off"
            className="mt-1 block w-full min-w-0 rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
          />
        </label>
        <label className="text-xs font-medium text-zinc-700 dark:text-zinc-300">
          {t('imports.cardcom.apiPasswordPlaceholder')}
          <input
            type="password" value={apiPassword} onChange={(event) => setApiPassword(event.target.value)}
            placeholder={t('imports.cardcom.apiPasswordPlaceholder')} dir="ltr" autoComplete="new-password"
            className="mt-1 block w-full min-w-0 rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
          />
        </label>
      </div>
      <p className="text-xs text-zinc-400 dark:text-zinc-500">{t('imports.cardcom.credentialsNote')}</p>
      <button
        type="submit"
        disabled={create.isPending || !isValid}
        className="rounded-md bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
      >
        {create.isPending ? t('common.saving') : t('imports.cardcom.addConnection')}
      </button>
      {error && <p className="text-sm text-danger-600 dark:text-danger-400">{error}</p>}
    </form>
  )
}

export function CardcomConnectionPanel() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const isOwner = user?.role === 'owner'
  const [showCreate, setShowCreate] = useState(false)
  const [newConnectionId, setNewConnectionId] = useState<string | null>(null)

  const { data, isLoading, isError } = useQuery({
    queryKey: CONNECTIONS_QUERY_KEY,
    queryFn: listConnections,
  })
  const cardcomConnections = (data ?? []).filter((connection) => connection.provider === 'cardcom')

  return (
    <div className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
      <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">{t('imports.cardcom.heading')}</h2>
      <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">{t('imports.cardcom.description')}</p>

      {isLoading && <p className="mt-4 text-sm text-zinc-500 dark:text-zinc-400">{t('common.loading')}</p>}
      {isError && <p className="mt-4 text-sm text-danger-600 dark:text-danger-400">{t('errors.generic')}</p>}

      {!isLoading && !isError && (
        <div className="mt-4 space-y-3">
          {cardcomConnections.length === 0 && <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-dashed border-zinc-300 p-4 dark:border-zinc-700"><p className="text-sm text-zinc-500 dark:text-zinc-400">{t('imports.cardcom.emptyState')}</p><span className="rounded-full bg-zinc-100 px-2.5 py-1 text-xs font-medium text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400">{t('imports.notConnected')}</span></div>}
          {cardcomConnections.map((connection) => (
            <ConnectionCard key={connection.id} connection={connection} startExpanded={connection.id === newConnectionId} />
          ))}
        </div>
      )}

      {isOwner ? (
        <div className="mt-4">
          <button type="button" onClick={() => setShowCreate((value) => !value)} aria-expanded={showCreate} className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700">
            {showCreate ? t('imports.cancelNewConnection') : t('imports.startConnection')}
          </button>
          {showCreate && <div className="mt-4 rounded-xl border border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-800/30">
            <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">{t('imports.stepCreate')}</p>
            <CreateConnectionForm onCreated={(id) => { setNewConnectionId(id); setShowCreate(false) }} />
            <p className="mt-3 text-xs text-zinc-500 dark:text-zinc-400">{t('imports.stepAfterCreate')}</p>
          </div>}
        </div>
      ) : (
        <p className="mt-4 text-xs text-zinc-400 dark:text-zinc-500">{t('imports.cardcom.ownerOnlyNote')}</p>
      )}
    </div>
  )
}
