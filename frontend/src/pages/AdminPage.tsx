import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Building2, Plus, ShieldCheck, Trash2, X } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Navigate } from 'react-router-dom'

import { useAuth } from '../contexts/AuthContext'
import { addBusinessProvider, deleteBusinessAsAdmin, listAdminBusinesses, type AdminBusiness } from '../services/adminService'
import type { PaymentProvider } from '../services/businessService'

const PROVIDER_LABELS: Record<PaymentProvider, string> = { grow: 'Grow', cardcom: 'Cardcom' }

export function AdminPage() {
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [deleteTarget, setDeleteTarget] = useState<AdminBusiness | null>(null)
  const [confirmName, setConfirmName] = useState('')
  const { data = [], isLoading, isError } = useQuery({ queryKey: ['admin-businesses'], queryFn: listAdminBusinesses })
  const addProvider = useMutation({
    mutationFn: ({ businessId, provider }: { businessId: string; provider: PaymentProvider }) => addBusinessProvider(businessId, provider),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin-businesses'] }),
  })
  const removeBusiness = useMutation({
    mutationFn: ({ businessId, name }: { businessId: string; name: string }) => deleteBusinessAsAdmin(businessId, name),
    onSuccess: () => {
      setDeleteTarget(null); setConfirmName('')
      queryClient.invalidateQueries({ queryKey: ['admin-businesses'] })
    },
  })
  const filtered = useMemo(() => {
    const term = search.trim().toLocaleLowerCase()
    if (!term) return data
    return data.filter((business) => [business.name, business.business_number, ...business.owner_emails]
      .some((value) => value?.toLocaleLowerCase().includes(term)))
  }, [data, search])

  if (user?.system_role !== 'admin') return <Navigate to="/app" replace />

  return <div className="space-y-6" dir="rtl">
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div><div className="flex items-center gap-2 text-brand-700"><ShieldCheck className="h-5 w-5"/><span className="text-sm font-semibold">ניהול מערכת</span></div><h1 className="mt-2 text-2xl font-semibold">עסקים במערכת</h1><p className="mt-1 text-sm text-stone-500">צפייה בעסקים, ספקי סליקה ונתוני שימוש מרכזיים.</p></div>
      <input aria-label="חיפוש עסקים" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="חיפוש לפי עסק, עוסק או אימייל" className="w-full max-w-sm rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm dark:border-stone-700 dark:bg-stone-900" />
    </div>
    {isLoading && <p className="text-sm text-stone-500">טוען עסקים…</p>}
    {isError && <p role="alert" className="rounded-lg bg-red-50 p-4 text-sm text-red-700">לא ניתן לטעון את רשימת העסקים.</p>}
    <div className="grid gap-4">
      {filtered.map((business) => <article key={business.id} className="rounded-xl border border-stone-200 bg-white p-5 shadow-sm dark:border-stone-700 dark:bg-stone-900">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex min-w-0 items-start gap-3"><span className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-brand-50 text-brand-700 dark:bg-brand-900"><Building2 className="h-5 w-5"/></span><div><h2 className="font-semibold text-stone-900 dark:text-stone-100">{business.name}</h2><p className="mt-1 text-xs text-stone-500" dir="ltr">{business.owner_emails.join(', ') || 'לא זמין'}</p><p className="mt-1 text-xs text-stone-400">{business.business_number ? `עוסק ${business.business_number}` : 'ללא מספר עוסק'} · נוצר {new Date(business.created_at).toLocaleDateString('he-IL')}</p></div></div>
          <button type="button" onClick={() => { setDeleteTarget(business); setConfirmName('') }} className="inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-red-600 hover:bg-red-50"><Trash2 className="h-4 w-4"/>מחיקת עסק</button>
        </div>
        <div className="mt-5 grid grid-cols-3 gap-3 rounded-lg bg-stone-50 p-3 text-center text-sm dark:bg-stone-800"><div><b className="block text-lg">{business.sale_count}</b>מכירות</div><div><b className="block text-lg">{business.connection_count}</b>חיבורים</div><div><b className="block text-lg">{business.member_count}</b>חברים</div></div>
        <div className="mt-4 flex flex-wrap items-center gap-2"><span className="me-1 text-sm font-medium">חברות סליקה:</span>{(['grow','cardcom'] as PaymentProvider[]).map((provider) => business.payment_providers.includes(provider)
          ? <span key={provider} className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700">{PROVIDER_LABELS[provider]}</span>
          : <button key={provider} type="button" disabled={addProvider.isPending} onClick={() => addProvider.mutate({ businessId: business.id, provider })} className="inline-flex items-center gap-1 rounded-full border border-dashed border-stone-300 px-3 py-1 text-xs text-stone-600 hover:border-brand-500 hover:text-brand-700"><Plus className="h-3 w-3"/>הוספת {PROVIDER_LABELS[provider]}</button>)}</div>
      </article>)}
    </div>
    {deleteTarget && <div className="fixed inset-0 z-50 grid place-items-center bg-stone-950/50 p-4" role="dialog" aria-modal="true" aria-labelledby="delete-business-title"><div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl dark:bg-stone-900"><div className="flex items-start justify-between gap-4"><div><h2 id="delete-business-title" className="text-lg font-semibold">מחיקה לצמיתות של {deleteTarget.name}</h2><p className="mt-2 text-sm text-stone-500">הפעולה תמחק את העסק ואת כל המכירות, החיבורים והיסטוריית הפעילות שלו. לא ניתן לבטל אותה.</p></div><button aria-label="סגירה" onClick={() => setDeleteTarget(null)}><X className="h-5 w-5"/></button></div><label className="mt-5 block text-sm font-medium">הקלידו את שם העסק לאישור<input autoFocus value={confirmName} onChange={(event) => setConfirmName(event.target.value)} className="mt-2 w-full rounded-lg border border-stone-300 px-3 py-2"/></label>{removeBusiness.isError && <p className="mt-3 text-sm text-red-600">מחיקת העסק נכשלה. ודאו שזה אינו העסק הפעיל של חשבון האדמין.</p>}<div className="mt-6 flex justify-end gap-2"><button onClick={() => setDeleteTarget(null)} className="rounded-lg px-4 py-2 text-sm">ביטול</button><button disabled={confirmName !== deleteTarget.name || removeBusiness.isPending} onClick={() => removeBusiness.mutate({ businessId: deleteTarget.id, name: confirmName })} className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-40">{removeBusiness.isPending ? 'מוחק…' : 'מחיקה לצמיתות'}</button></div></div></div>}
  </div>
}
