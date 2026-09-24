import { useState, type FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'

import { useAuth } from '../contexts/AuthContext'
import { apiClient, toApiError } from '../services/apiClient'
import { FormField, inputClasses } from '../components/FormField'
import { buttonClasses } from '../components/ui-classes'

export function SupportLoginPage() {
  const { user, setUser } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  if (user?.system_role === 'support' || user?.system_role === 'admin') return <Navigate to="/support" replace />
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError('')
    try {
      const { data } = await apiClient.post('/auth/login', { email: email.trim(), password })
      if (data.user.system_role !== 'support' && data.user.system_role !== 'admin') {
        await apiClient.post('/auth/logout')
        setError('לחשבון הזה אין הרשאת תמיכה.')
        return
      }
      queryClient.clear(); setUser(data.user); navigate('/support', { replace: true })
    } catch (failure) { setError(toApiError(failure).message) }
    finally { setBusy(false) }
  }
  return <main dir="rtl" className="mx-auto flex min-h-screen max-w-md flex-col justify-center gap-6 p-6"><div><p className="text-sm font-medium text-brand-700">Sydney</p><h1 className="mt-2 text-3xl font-semibold">כניסה לממשק התמיכה</h1></div><form onSubmit={submit} className="space-y-5 rounded-xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900"><FormField label="אימייל תמיכה" htmlFor="staff-email"><input id="staff-email" dir="ltr" type="email" autoComplete="username" required className={inputClasses} value={email} onChange={event => setEmail(event.target.value)} /></FormField><FormField label="סיסמה" htmlFor="staff-password"><input id="staff-password" dir="ltr" type="password" autoComplete="current-password" required className={inputClasses} value={password} onChange={event => setPassword(event.target.value)} /></FormField>{error && <p role="alert" className="text-sm text-danger-700">{error}</p>}<button className={buttonClasses('primary')} disabled={busy}>{busy ? 'מתחברים…' : 'כניסה'}</button></form></main>
}
