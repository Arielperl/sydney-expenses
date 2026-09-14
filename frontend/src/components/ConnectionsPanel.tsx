import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, Copy, KeyRound, Link2, Power, RefreshCcw } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import { API_BASE_URL, ApiError } from '../services/apiClient'
import { createConnection, listConnections, rotateConnectionSecret, setConnectionEnabled } from '../services/connectionService'
import type { ConnectionWithSecret } from '../types/connections'

export function ConnectionsPanel() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [revealed, setRevealed] = useState<ConnectionWithSecret | null>(null)
  const [copied, setCopied] = useState<'url' | 'secret' | null>(null)

  const connections = useQuery({ queryKey: ['connections'], queryFn: listConnections })
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['connections'] })
  const create = useMutation({
    mutationFn: () => createConnection(name.trim() || t('imports.connections.defaultName')),
    onSuccess: (result) => { setName(''); setRevealed(result); void refresh() },
  })
  const toggle = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) => setConnectionEnabled(id, enabled),
    onSuccess: () => void refresh(),
  })
  const rotate = useMutation({
    mutationFn: rotateConnectionSecret,
    onSuccess: (result) => { setRevealed(result); void refresh() },
  })
  const error = connections.error || create.error || toggle.error || rotate.error

  async function copy(value: string, kind: 'url' | 'secret') {
    await navigator.clipboard?.writeText(value)
    setCopied(kind)
    window.setTimeout(() => setCopied(null), 1500)
  }

  const fullUrl = (path: string) => `${API_BASE_URL.replace(/\/$/, '')}${path}`

  return (
    <section className="rounded-2xl border border-stone-200 bg-white p-6 shadow-sm dark:border-stone-800 dark:bg-stone-900" aria-labelledby="connections-heading">
      <div className="flex items-start gap-3">
        <div className="rounded-xl bg-brand-50 p-2.5 text-brand-600 dark:bg-brand-950/40 dark:text-brand-400"><Link2 size={20} /></div>
        <div>
          <h2 id="connections-heading" className="text-base font-semibold text-stone-900 dark:text-stone-100">{t('imports.connections.heading')}</h2>
          <p className="mt-1 text-sm text-stone-600 dark:text-stone-400">{t('imports.connections.description')}</p>
        </div>
      </div>

      <form className="mt-5 flex flex-col gap-3 sm:flex-row" onSubmit={(event) => { event.preventDefault(); create.mutate() }}>
        <label className="sr-only" htmlFor="connection-name">{t('imports.connections.nameLabel')}</label>
        <input id="connection-name" value={name} onChange={(event) => setName(event.target.value)} maxLength={100}
          placeholder={t('imports.connections.namePlaceholder')}
          className="min-w-0 flex-1 rounded-xl border border-stone-300 bg-white px-4 py-2.5 text-sm text-stone-900 outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100 dark:border-stone-700 dark:bg-stone-950 dark:text-stone-100" />
        <button type="submit" disabled={create.isPending}
          className="rounded-xl bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50">
          {create.isPending ? t('imports.connections.creating') : t('imports.connections.create')}
        </button>
      </form>

      {error && <p role="alert" className="mt-3 text-sm text-red-600">{error instanceof ApiError ? error.message : t('common.somethingWentWrong')}</p>}

      {revealed && (
        <div className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-4 dark:border-amber-900 dark:bg-amber-950/30">
          <div className="flex items-center gap-2 font-semibold text-amber-900 dark:text-amber-200"><KeyRound size={18} />{t('imports.connections.secretTitle')}</div>
          <p className="mt-1 text-xs text-amber-800 dark:text-amber-300">{t('imports.connections.secretWarning')}</p>
          <SecretRow label={t('imports.connections.webhookUrl')} value={fullUrl(revealed.webhook_path)} copied={copied === 'url'} onCopy={() => void copy(fullUrl(revealed.webhook_path), 'url')} />
          <SecretRow label={t('imports.connections.signingSecret')} value={revealed.signing_secret} copied={copied === 'secret'} onCopy={() => void copy(revealed.signing_secret, 'secret')} />
          <button type="button" onClick={() => setRevealed(null)} className="mt-3 text-xs font-semibold text-amber-900 underline dark:text-amber-200">{t('common.close')}</button>
        </div>
      )}

      <div className="mt-5 space-y-3">
        {connections.isLoading && <p className="text-sm text-stone-500">{t('common.loading')}</p>}
        {connections.data?.length === 0 && <p className="rounded-xl bg-stone-50 p-4 text-sm text-stone-500 dark:bg-stone-950 dark:text-stone-400">{t('imports.connections.empty')}</p>}
        {connections.data?.map((connection) => (
          <div key={connection.id} className="flex flex-col gap-3 rounded-xl border border-stone-200 p-4 dark:border-stone-800 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="flex items-center gap-2">
                <span className="font-medium text-stone-900 dark:text-stone-100">{connection.name}</span>
                <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${connection.enabled ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300' : 'bg-stone-100 text-stone-500 dark:bg-stone-800 dark:text-stone-400'}`}>
                  {connection.enabled ? t('imports.connections.active') : t('imports.connections.inactive')}
                </span>
              </div>
              <p className="mt-1 text-xs text-stone-500">demo-pay · {connection.last_event_at ? t('imports.connections.lastEvent', { date: new Date(connection.last_event_at).toLocaleString() }) : t('imports.connections.noEvents')}</p>
            </div>
            <div className="flex gap-2">
              <button type="button" disabled={toggle.isPending} onClick={() => toggle.mutate({ id: connection.id, enabled: !connection.enabled })}
                className="inline-flex items-center gap-1.5 rounded-lg border border-stone-300 px-3 py-2 text-xs font-semibold text-stone-700 hover:bg-stone-50 disabled:opacity-50 dark:border-stone-700 dark:text-stone-300 dark:hover:bg-stone-800">
                <Power size={14} />{connection.enabled ? t('imports.connections.disable') : t('imports.connections.enable')}
              </button>
              <button type="button" disabled={rotate.isPending} onClick={() => { if (window.confirm(t('imports.connections.rotateConfirm'))) rotate.mutate(connection.id) }}
                className="inline-flex items-center gap-1.5 rounded-lg border border-stone-300 px-3 py-2 text-xs font-semibold text-stone-700 hover:bg-stone-50 disabled:opacity-50 dark:border-stone-700 dark:text-stone-300 dark:hover:bg-stone-800">
                <RefreshCcw size={14} />{t('imports.connections.rotate')}
              </button>
            </div>
          </div>
        ))}
      </div>

      <p className="mt-5 text-xs text-stone-500 dark:text-stone-400">{t('imports.connections.demoDisclaimer')}</p>
    </section>
  )
}

function SecretRow({ label, value, copied, onCopy }: { label: string; value: string; copied: boolean; onCopy: () => void }) {
  const { t } = useTranslation()
  return <div className="mt-3"><div className="mb-1 text-xs font-medium text-amber-900 dark:text-amber-200">{label}</div><div className="flex gap-2" dir="ltr"><code className="min-w-0 flex-1 overflow-x-auto rounded-lg bg-white px-3 py-2 text-xs text-stone-800 dark:bg-stone-950 dark:text-stone-200">{value}</code><button type="button" onClick={onCopy} aria-label={t('imports.connections.copy', { label })} className="rounded-lg border border-amber-300 bg-white px-3 text-amber-900 dark:border-amber-800 dark:bg-stone-950 dark:text-amber-200">{copied ? <Check size={16} /> : <Copy size={16} />}</button></div></div>
}
