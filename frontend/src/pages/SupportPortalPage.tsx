import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'

import { ConfirmDialog } from '../components/ConfirmDialog'
import { Modal } from '../components/Modal'
import { FormField, inputClasses } from '../components/FormField'
import { Card } from '../components/ui'
import { buttonClasses } from '../components/ui-classes'
import { useAuth } from '../contexts/AuthContext'
import {
  addBusinessProvider, createStaffUser, deleteStaffUser, listAdminBusinesses,
  listStaffUsers, removeBusinessProvider, updateStaffUserRole,
  type ManagedRole, type StaffUser, type StaffUserCreate,
} from '../services/adminService'
import { listStaffSupportRequests, setSupportRequestStatus } from '../services/supportService'
import type { PaymentProvider } from '../services/businessService'

const roleLabels: Record<ManagedRole | 'superadmin', string> = {
  user: 'משתמש', support: 'תמיכה', admin: 'אדמין', superadmin: 'סופר אדמין',
}
const emptyAccount: StaffUserCreate = { email: '', password: '', name: '', system_role: 'support' }

export function SupportPortalPage() {
  const { user, logout } = useAuth()
  const queryClient = useQueryClient()
  const isSuperadmin = user?.system_role === 'superadmin'
  const [search, setSearch] = useState('')
  const [removal, setRemoval] = useState<{ businessId: string; businessName: string; provider: PaymentProvider } | null>(null)
  const [userRemoval, setUserRemoval] = useState<StaffUser | null>(null)
  const [confirmEmail, setConfirmEmail] = useState('')
  const [showCreateAccount, setShowCreateAccount] = useState(false)
  const [account, setAccount] = useState<StaffUserCreate>(emptyAccount)

  const requests = useQuery({ queryKey: ['staff-requests'], queryFn: listStaffSupportRequests })
  const businesses = useQuery({ queryKey: ['staff-businesses'], queryFn: listAdminBusinesses })
  const users = useQuery({ queryKey: ['staff-users'], queryFn: listStaffUsers, enabled: isSuperadmin })
  const refreshUsers = () => void queryClient.invalidateQueries({ queryKey: ['staff-users'] })
  const changeStatus = useMutation({ mutationFn: ({ id, status }: { id: string; status: 'open' | 'resolved' }) => setSupportRequestStatus(id, status), onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['staff-requests'] }) })
  const addProvider = useMutation({ mutationFn: ({ businessId, provider }: { businessId: string; provider: PaymentProvider }) => addBusinessProvider(businessId, provider), onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['staff-businesses'] }) })
  const removeProvider = useMutation({ mutationFn: ({ businessId, provider }: { businessId: string; provider: PaymentProvider }) => removeBusinessProvider(businessId, provider), onSuccess: () => { setRemoval(null); void queryClient.invalidateQueries({ queryKey: ['staff-businesses'] }) } })
  const removeUser = useMutation({ mutationFn: deleteStaffUser, onSuccess: () => { setUserRemoval(null); setConfirmEmail(''); refreshUsers() } })
  const createUser = useMutation({ mutationFn: createStaffUser, onSuccess: () => { setAccount(emptyAccount); setShowCreateAccount(false); refreshUsers() } })
  const changeRole = useMutation({ mutationFn: ({ id, role }: { id: string; role: ManagedRole }) => updateStaffUserRole(id, role), onSuccess: refreshUsers })
  const shownBusinesses = businesses.data?.filter(item => [item.name, ...item.owner_emails].some(value => value.toLowerCase().includes(search.toLowerCase()))) ?? []

  function submitAccount(event: FormEvent) {
    event.preventDefault()
    createUser.mutate({ ...account, email: account.email.trim(), name: account.name.trim() })
  }

  return <main dir="rtl" className="min-h-screen bg-zinc-50 p-5 text-zinc-900 dark:bg-zinc-950 dark:text-zinc-50 md:p-10"><div className="mx-auto max-w-6xl space-y-8">
    <header className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-sm font-medium text-brand-700">Sydney Support</p><h1 className="text-3xl font-semibold">ממשק תמיכה</h1><p className="mt-1 text-sm text-zinc-500" dir="ltr">{user?.email}</p></div><button className={buttonClasses('secondary')} onClick={() => void logout()}>התנתקות</button></header>

    <section aria-labelledby="requests-heading" className="space-y-4"><div className="flex items-center justify-between"><h2 id="requests-heading" className="text-xl font-semibold">פניות מבעלי עסקים</h2><span className="text-sm text-zinc-500">{requests.data?.filter(item => item.status === 'open').length ?? 0} פתוחות</span></div>
      {requests.isLoading && <p>טוענים פניות…</p>}{requests.isError && <p role="alert">לא ניתן לטעון פניות.</p>}{requests.data?.length === 0 && <Card className="p-5">אין פניות כרגע.</Card>}
      <div className="grid gap-3">{requests.data?.map(item => <Card key={item.id} className="p-5"><div className="flex flex-wrap justify-between gap-2"><div><h3 className="font-semibold">{item.subject}</h3><p className="text-sm text-zinc-500">{item.business_name} · <span dir="ltr">{item.requester_email}</span> · {new Date(item.created_at).toLocaleString('he-IL')}</p></div><span className="text-sm">{item.status === 'open' ? 'פתוחה' : 'טופלה'}</span></div>{item.provider && <p className="mt-2 text-sm">חברה: {item.provider}</p>}<p className="my-3 whitespace-pre-wrap text-sm leading-6">{item.message}</p><button className={buttonClasses('secondary', 'sm')} disabled={changeStatus.isPending} onClick={() => changeStatus.mutate({ id: item.id, status: item.status === 'open' ? 'resolved' : 'open' })}>{item.status === 'open' ? 'סימון כטופלה' : 'פתיחה מחדש'}</button></Card>)}</div>
    </section>

    <section aria-labelledby="businesses-heading" className="space-y-4"><h2 id="businesses-heading" className="text-xl font-semibold">עסקים וחברות סליקה</h2><input type="search" aria-label="חיפוש עסק או בעלים" className="w-full max-w-md rounded-lg border border-zinc-300 bg-white p-2 dark:border-zinc-700 dark:bg-zinc-900" value={search} onChange={event => setSearch(event.target.value)} />{businesses.isLoading && <p>טוענים עסקים…</p>}{businesses.isError && <p role="alert">לא ניתן לטעון עסקים.</p>}
      <div className="grid gap-4 md:grid-cols-2">{shownBusinesses.map(business => <Card key={business.id} className="p-5"><h3 className="font-semibold">{business.name}</h3><p className="mt-1 text-sm text-zinc-500" dir="ltr">{business.owner_emails.join(', ')}</p><p className="mt-2 text-sm text-zinc-500">{business.sale_count} מכירות · {business.connection_count} חיבורים</p><div className="mt-4 flex flex-wrap gap-2">{(['grow', 'cardcom'] as PaymentProvider[]).map(provider => business.payment_providers.includes(provider) ? <button key={provider} className={buttonClasses('secondary', 'sm')} onClick={() => setRemoval({ businessId: business.id, businessName: business.name, provider })}>הסרת {provider === 'grow' ? 'Grow' : 'Cardcom'}</button> : <button key={provider} disabled={addProvider.isPending} className={buttonClasses('primary', 'sm')} onClick={() => addProvider.mutate({ businessId: business.id, provider })}>הוספת {provider === 'grow' ? 'Grow' : 'Cardcom'}</button>)}</div></Card>)}</div>
      {(addProvider.isError || removeProvider.isError || changeStatus.isError) && <p role="alert" className="text-sm text-danger-700">הפעולה נכשלה. נסו שוב.</p>}
    </section>

    {isSuperadmin && <section aria-labelledby="users-heading" className="space-y-4"><div className="flex flex-wrap items-center justify-between gap-3"><div><h2 id="users-heading" className="text-xl font-semibold">חשבונות והרשאות</h2><p className="text-sm text-zinc-500">רק סופר אדמין יכול ליצור חשבונות, לשנות תפקידים ולמחוק משתמשים.</p></div><button className={buttonClasses('primary')} onClick={() => setShowCreateAccount(true)}>יצירת חשבון</button></div>
      {users.isLoading && <p>טוענים משתמשים…</p>}{users.isError && <p role="alert">לא ניתן לטעון משתמשים.</p>}
      <div className="grid gap-3">{users.data?.map(item => <Card key={item.id} className="flex flex-wrap items-center justify-between gap-3 p-4"><div><p className="font-medium" dir="ltr">{item.email}</p><p className="text-sm text-zinc-500">{item.business_name || 'ללא עסק'} · {roleLabels[item.system_role]}</p></div><div className="flex flex-wrap items-center gap-2">{item.system_role !== 'superadmin' && <select aria-label={`תפקיד עבור ${item.email}`} className={`${inputClasses} w-auto`} value={item.system_role} disabled={changeRole.isPending} onChange={event => changeRole.mutate({ id: item.id, role: event.target.value as ManagedRole })}><option value="user">משתמש</option><option value="support">תמיכה</option><option value="admin">אדמין</option></select>}{item.id !== user.id && item.system_role !== 'superadmin' && <button className={buttonClasses('danger', 'sm')} onClick={() => { setUserRemoval(item); setConfirmEmail('') }}>מחיקת משתמש</button>}</div></Card>)}</div>
      {changeRole.isError && <p role="alert" className="text-sm text-danger-700">שינוי התפקיד נכשל.</p>}
    </section>}

    {showCreateAccount && <Modal title="יצירת חשבון" onClose={() => { setShowCreateAccount(false); createUser.reset() }}><form className="space-y-4" onSubmit={submitAccount}><FormField label="שם" htmlFor="new-account-name"><input id="new-account-name" className={inputClasses} value={account.name} onChange={event => setAccount({ ...account, name: event.target.value })} /></FormField><FormField label="שם התחברות" htmlFor="new-account-email" hint={account.system_role === 'user' ? 'למשתמש רגיל הזינו כתובת אימייל מלאה.' : 'לדוגמה: liad@support'}><input id="new-account-email" dir="ltr" type="text" autoComplete="off" required placeholder={account.system_role === 'user' ? 'name@example.com' : 'liad@support'} className={inputClasses} value={account.email} onChange={event => setAccount({ ...account, email: event.target.value })} /></FormField><FormField label="סיסמה זמנית — לפחות 12 תווים" htmlFor="new-account-password"><input id="new-account-password" dir="ltr" type="password" autoComplete="new-password" required minLength={12} className={inputClasses} value={account.password} onChange={event => setAccount({ ...account, password: event.target.value })} /></FormField><FormField label="תפקיד" htmlFor="new-account-role"><select id="new-account-role" className={inputClasses} value={account.system_role} onChange={event => setAccount({ ...account, system_role: event.target.value as ManagedRole })}><option value="support">תמיכה</option><option value="admin">אדמין</option><option value="user">משתמש</option></select></FormField>{createUser.isError && <p role="alert" className="text-sm text-danger-700">{createUser.error.message}</p>}<div className="flex gap-2"><button type="button" className={buttonClasses('secondary')} onClick={() => setShowCreateAccount(false)}>ביטול</button><button type="submit" className={buttonClasses('primary')} disabled={createUser.isPending}>{createUser.isPending ? 'יוצרים…' : 'יצירת חשבון'}</button></div></form></Modal>}
    {removal && <ConfirmDialog title={`הסרת ${removal.provider}`} description={`החיבור הפעיל של ${removal.businessName} יושבת. האם להמשיך?`} confirmLabel="הסרה" isLoading={removeProvider.isPending} error={removeProvider.isError ? 'ההסרה נכשלה' : null} onClose={() => setRemoval(null)} onConfirm={() => removeProvider.mutate({ businessId: removal.businessId, provider: removal.provider })} />}
    {userRemoval && <Modal title={`מחיקת ${userRemoval.email}`} onClose={() => setUserRemoval(null)}><p className="text-sm text-zinc-600 dark:text-zinc-400">הפעולה תבטל את גישת המשתמש ותסיר את שיוכו לעסק. נתוני העסק והמכירות יישמרו.</p><div className="mt-4"><FormField label="להמשך, הקלידו את שם ההתחברות של המשתמש" htmlFor="confirm-delete-user"><input id="confirm-delete-user" dir="ltr" className={inputClasses} value={confirmEmail} onChange={event => setConfirmEmail(event.target.value)} /></FormField></div>{removeUser.isError && <p role="alert" className="mt-3 text-sm text-danger-700">{removeUser.error.message}</p>}<div className="mt-5 flex gap-2"><button className={buttonClasses('secondary')} onClick={() => setUserRemoval(null)}>ביטול</button><button className={buttonClasses('danger')} disabled={confirmEmail !== userRemoval.email || removeUser.isPending} onClick={() => removeUser.mutate(userRemoval.id)}>{removeUser.isPending ? 'מוחקים…' : 'מחיקת משתמש'}</button></div></Modal>}
  </div></main>
}
