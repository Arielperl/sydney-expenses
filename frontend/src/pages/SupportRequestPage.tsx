import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Maximize2, MessageCircle, Plus } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { FormField, inputClasses } from '../components/FormField'
import { Modal } from '../components/Modal'
import { SupportConversationDialog } from '../components/SupportConversationDialog'
import { Badge, Card, PageHeader } from '../components/ui'
import { buttonClasses } from '../components/ui-classes'
import { createSupportRequest, listOwnSupportRequests } from '../services/supportService'

export function SupportRequestPage() {
  const { i18n } = useTranslation()
  const english = i18n.language.startsWith('en')
  const queryClient = useQueryClient()
  const [provider, setProvider] = useState('')
  const [subject, setSubject] = useState('')
  const [message, setMessage] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [sentNotice, setSentNotice] = useState(false)
  const [selectedRequestId, setSelectedRequestId] = useState<string | null>(null)
  const requests = useQuery({
    queryKey: ['support-requests-own'],
    queryFn: listOwnSupportRequests,
    refetchInterval: selectedRequestId ? 3_000 : 15_000,
    refetchOnWindowFocus: 'always',
  })
  const create = useMutation({
    mutationFn: createSupportRequest,
    onSuccess: () => {
      setSubject('')
      setMessage('')
      setProvider('')
      setShowCreate(false)
      setSentNotice(true)
      void queryClient.invalidateQueries({ queryKey: ['support-requests-own'] })
    },
  })

  function submit(event: FormEvent) {
    event.preventDefault()
    create.mutate({ subject: subject.trim(), message: message.trim(), provider: provider || undefined })
  }

  function openCreateForm() {
    create.reset()
    setSentNotice(false)
    setShowCreate(true)
  }

  const selectedRequest = requests.data?.find(item => item.id === selectedRequestId)
  const openCount = requests.data?.filter(item => item.status === 'open').length ?? 0

  return <div className="max-w-4xl space-y-6">
    <PageHeader
      title={english ? 'Support and requests' : 'תמיכה ופניות'}
      description={english ? 'Track your conversations with Sydney support or open a new request.' : 'עקבו אחר השיחות שלכם עם צוות Sydney או פתחו פנייה חדשה.'}
      actions={<button type="button" className={buttonClasses('primary')} onClick={openCreateForm}><Plus className="h-4 w-4" aria-hidden="true" />{english ? 'New request' : 'פנייה חדשה'}</button>}
    />

    {sentNotice && <p role="status" className="rounded-xl border border-success-500/20 bg-success-50 px-4 py-3 text-sm text-success-700 dark:bg-success-500/10 dark:text-success-500">{english ? 'Your request was sent. The support team can now reply in the conversation.' : 'הפנייה נשלחה. צוות התמיכה יוכל לענות לכם ישירות בשיחה.'}</p>}

    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-200 px-5 py-4 dark:border-zinc-800">
        <div>
          <h2 className="text-lg font-semibold">{english ? 'Your requests' : 'הפניות שלכם'}</h2>
          <p className="mt-0.5 text-sm text-zinc-500">{english ? `${openCount} open requests` : `${openCount} פניות פתוחות`}</p>
        </div>
      </div>

      {requests.isLoading && <p className="p-5" role="status">{english ? 'Loading…' : 'טוענים…'}</p>}
      {requests.isError && <p className="p-5 text-danger-700" role="alert">{english ? 'Could not load requests.' : 'לא ניתן לטעון פניות.'}</p>}
      {requests.data?.length === 0 && <div className="grid place-items-center gap-3 px-5 py-12 text-center"><span className="grid h-11 w-11 place-items-center rounded-full bg-brand-50 text-brand-700 dark:bg-brand-500/10 dark:text-brand-300"><MessageCircle className="h-5 w-5" aria-hidden="true" /></span><div><p className="font-medium">{english ? 'No requests yet' : 'עדיין אין פניות'}</p><p className="mt-1 text-sm text-zinc-500">{english ? 'Open a request whenever you need help.' : 'כשתצטרכו עזרה, תוכלו לפתוח מכאן פנייה חדשה.'}</p></div><button type="button" className={buttonClasses('secondary', 'sm')} onClick={openCreateForm}>{english ? 'Open first request' : 'פתיחת פנייה ראשונה'}</button></div>}

      <ul className="divide-y divide-zinc-200 dark:divide-zinc-800">{requests.data?.map(item => <li key={item.id} className="p-5"><div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between"><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><h3 className="font-semibold text-zinc-900 dark:text-zinc-50">{item.subject}</h3><Badge tone={item.status === 'open' ? 'warning' : 'success'}>{item.status === 'open' ? (english ? 'Open' : 'פתוחה') : (english ? 'Resolved' : 'טופלה')}</Badge></div><p className="mt-1.5 line-clamp-2 whitespace-pre-wrap text-sm leading-6 text-zinc-600 dark:text-zinc-400">{item.message}</p><p className="mt-2 text-xs text-zinc-500">{item.provider && <>{english ? 'Provider' : 'חברה'}: {item.provider} · </>}<time dateTime={item.updated_at}>{new Date(item.updated_at).toLocaleString(english ? 'en-US' : 'he-IL')}</time></p></div><button type="button" className={buttonClasses('secondary', 'sm', 'shrink-0')} onClick={() => setSelectedRequestId(item.id)}><Maximize2 className="h-4 w-4" aria-hidden="true" />{english ? 'Open conversation' : 'פתיחת השיחה'}</button></div></li>)}</ul>
    </Card>

    <Link to="/imports" className={buttonClasses('secondary')}>{english ? 'Back to data import' : 'חזרה לייבוא נתונים'}</Link>

    {showCreate && <Modal title={english ? 'New support request' : 'פתיחת פנייה חדשה'} onClose={() => setShowCreate(false)}><form onSubmit={submit} className="space-y-5">
      <FormField label={english ? 'Payment provider' : 'חברת סליקה'} htmlFor="support-provider"><select id="support-provider" value={provider} onChange={event => setProvider(event.target.value)} className={inputClasses}><option value="">{english ? 'Other or general question' : 'אחר או שאלה כללית'}</option><option value="grow">Grow</option><option value="cardcom">Cardcom</option><option value="tabit">Tabit</option><option value="cal">כאל / Cal</option></select></FormField>
      <FormField label={english ? 'Subject' : 'נושא'} htmlFor="support-subject"><input id="support-subject" className={inputClasses} required minLength={3} maxLength={160} value={subject} onChange={event => setSubject(event.target.value)} /></FormField>
      <FormField label={english ? 'How can we help?' : 'איך נוכל לעזור?'} htmlFor="support-message"><textarea id="support-message" className={`${inputClasses} min-h-32`} required minLength={10} maxLength={5000} value={message} onChange={event => setMessage(event.target.value)} /></FormField>
      {create.isError && <p role="alert" className="text-sm text-danger-700">{create.error.message}</p>}
      <div className="flex flex-wrap gap-2"><button type="submit" disabled={create.isPending} className={buttonClasses('primary')}>{create.isPending ? (english ? 'Sending…' : 'שולחים…') : (english ? 'Send request' : 'שליחת פנייה')}</button><button type="button" disabled={create.isPending} className={buttonClasses('secondary')} onClick={() => setShowCreate(false)}>{english ? 'Cancel' : 'ביטול'}</button></div>
    </form></Modal>}
    {selectedRequest && <SupportConversationDialog request={selectedRequest} staff={false} english={english} onClose={() => setSelectedRequestId(null)} />}
  </div>
}
