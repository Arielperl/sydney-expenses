import { useState, type FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { LockKeyhole } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import { useAuth } from '../contexts/AuthContext'
import { apiClient, toApiError } from '../services/apiClient'
import { FormField, inputClasses } from '../components/FormField'
import { LanguageSwitcher } from '../components/LanguageSwitcher'
import { ThemeSwitcher } from '../components/ThemeSwitcher'
import { Card } from '../components/ui'
import { buttonClasses } from '../components/ui-classes'
import { SupportBrand } from './SupportPortalPage'

const STAFF_ROLES = ['support', 'admin', 'superadmin']

export function SupportLoginPage() {
  const { t } = useTranslation()
  const { user, setUser } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  if (user && STAFF_ROLES.includes(user.system_role)) return <Navigate to="/support" replace />

  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError('')
    try {
      const { data } = await apiClient.post('/auth/login', { email: email.trim(), password })
      if (!STAFF_ROLES.includes(data.user.system_role)) {
        await apiClient.post('/auth/logout')
        setError(t('supportPortal.login.noPermission'))
        return
      }
      queryClient.clear(); setUser(data.user); navigate('/support', { replace: true })
    } catch (failure) { setError(toApiError(failure).message) }
    finally { setBusy(false) }
  }

  return (
    <div className="flex min-h-screen flex-col bg-zinc-50 dark:bg-zinc-950">
      <header className="flex items-center justify-between gap-3 px-4 py-4 sm:px-6">
        <SupportBrand />
        <div className="flex items-center gap-1">
          <LanguageSwitcher placement="bottom" />
          <ThemeSwitcher />
        </div>
      </header>
      <main className="flex flex-1 items-start justify-center px-4 pt-8 pb-16 sm:items-center sm:pt-0">
        <Card className="w-full max-w-sm animate-page-enter p-6 sm:p-7">
          <span className="grid h-10 w-10 place-items-center rounded-lg bg-brand-50 text-brand-700 ring-1 ring-brand-100 dark:bg-brand-500/10 dark:text-brand-300 dark:ring-brand-500/20" aria-hidden="true">
            <LockKeyhole className="h-5 w-5" />
          </span>
          <h1 className="mt-4 text-xl font-semibold text-zinc-900 dark:text-zinc-50">{t('supportPortal.login.title')}</h1>
          <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">{t('supportPortal.login.description')}</p>
          <form onSubmit={submit} className="mt-6 space-y-4">
            <FormField label={t('supportPortal.login.username')} htmlFor="staff-email">
              <input id="staff-email" dir="ltr" type="text" autoComplete="username" required className={inputClasses} value={email} onChange={(event) => setEmail(event.target.value)} />
            </FormField>
            <FormField label={t('supportPortal.login.password')} htmlFor="staff-password">
              <input id="staff-password" dir="ltr" type="password" autoComplete="current-password" required className={inputClasses} value={password} onChange={(event) => setPassword(event.target.value)} />
            </FormField>
            {error && <p role="alert" className="rounded-lg bg-danger-50 px-3 py-2 text-sm text-danger-700 dark:bg-danger-500/10 dark:text-danger-500">{error}</p>}
            <button type="submit" className={buttonClasses('primary', 'md', 'w-full')} disabled={busy}>
              {busy ? t('supportPortal.login.submitting') : t('supportPortal.login.submit')}
            </button>
          </form>
        </Card>
      </main>
    </div>
  )
}
