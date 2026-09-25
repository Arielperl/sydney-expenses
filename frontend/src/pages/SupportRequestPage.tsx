import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Maximize2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { FormField, inputClasses } from '../components/FormField'
import { SupportConversationDialog } from '../components/SupportConversationDialog'
import { Card, PageHeader } from '../components/ui'
import { buttonClasses } from '../components/ui-classes'
import { createSupportRequest, listOwnSupportRequests } from '../services/supportService'

export function SupportRequestPage() {
  const { i18n } = useTranslation()
  const english = i18n.language.startsWith('en')
  const queryClient = useQueryClient()
  const [provider, setProvider] = useState('')
  const [subject, setSubject] = useState('')
  const [message, setMessage] = useState('')
  const [selectedRequestId, setSelectedRequestId] = useState<string | null>(null)
  const requests = useQuery({
    queryKey: ['support-requests-own'],
    queryFn: listOwnSupportRequests,
    refetchInterval: selectedRequestId ? 3_000 : 15_000,
    refetchOnWindowFocus: 'always',
  })
  const create = useMutation({ mutationFn: createSupportRequest, onSuccess: () => {
    setSubject(''); setMessage(''); setProvider('')
    void queryClient.invalidateQueries({ queryKey: ['support-requests-own'] })
  } })
  function submit(event: FormEvent) {
    event.preventDefault()
    create.mutate({ subject: subject.trim(), message: message.trim(), provider: provider || undefined })
  }
  const selectedRequest = requests.data?.find(item => item.id === selectedRequestId)
  return <div className="max-w-3xl space-y-6">
    <PageHeader title={english ? 'Contact support' : 'פנייה לתמיכה'} description={english ? 'Tell us which payment provider you use and what you need. Your request is linked to your business automatically.' : 'ספרו לנו עם איזו חברת סליקה אתם עובדים ומה אתם צריכים. הפנייה תשויך לעסק שלכם אוטומטית.'} />
    <Card className="p-6"><form onSubmit={submit} className="space-y-5">
      <FormField label={english ? 'Payment provider' : 'חברת סליקה'} htmlFor="support-provider"><select id="support-provider" value={provider} onChange={event => setProvider(event.target.value)} className={inputClasses}><option value="">{english ? 'Other or general question' : 'אחר או שאלה כללית'}</option><option value="grow">Grow</option><option value="cardcom">Cardcom</option><option value="tabit">Tabit</option><option value="cal">כאל / Cal</option></select></FormField>
      <FormField label={english ? 'Subject' : 'נושא'} htmlFor="support-subject"><input id="support-subject" className={inputClasses} required minLength={3} maxLength={160} value={subject} onChange={event => setSubject(event.target.value)} /></FormField>
      <FormField label={english ? 'How can we help?' : 'איך נוכל לעזור?'} htmlFor="support-message"><textarea id="support-message" className={`${inputClasses} min-h-32`} required minLength={10} maxLength={5000} value={message} onChange={event => setMessage(event.target.value)} /></FormField>
      {create.isError && <p role="alert" className="text-sm text-danger-700">{create.error.message}</p>}
      {create.isSuccess && <p role="status" className="text-sm text-success-700">{english ? 'Your request was sent.' : 'הפנייה נשלחה בהצלחה.'}</p>}
      <button type="submit" disabled={create.isPending} className={buttonClasses('primary')}>{create.isPending ? (english ? 'Sending…' : 'שולחים…') : (english ? 'Send request' : 'שליחת פנייה')}</button>
    </form></Card>
    <Card className="p-6"><h2 className="mb-4 text-lg font-semibold">{english ? 'Your requests' : 'הפניות שלכם'}</h2>
      {requests.isLoading && <p>{english ? 'Loading…' : 'טוענים…'}</p>}
      {requests.isError && <p role="alert">{english ? 'Could not load requests.' : 'לא ניתן לטעון פניות.'}</p>}
      {requests.data?.length === 0 && <p className="text-sm text-zinc-500">{english ? 'No requests yet.' : 'עדיין אין פניות.'}</p>}
      <ul className="divide-y divide-zinc-200 dark:divide-zinc-800">{requests.data?.map(item => <li key={item.id} className="py-4"><div className="flex flex-wrap items-start justify-between gap-3"><div className="min-w-0"><strong>{item.subject}</strong><p className="mt-1 line-clamp-2 whitespace-pre-wrap text-sm text-zinc-600 dark:text-zinc-400">{item.message}</p></div><div className="flex shrink-0 items-center gap-2"><span className="text-sm">{item.status === 'open' ? (english ? 'Open' : 'פתוחה') : (english ? 'Resolved' : 'טופלה')}</span><button type="button" className={buttonClasses('secondary', 'sm')} onClick={() => setSelectedRequestId(item.id)}><Maximize2 className="h-4 w-4" aria-hidden="true" />{english ? 'Open full screen' : 'פתיחה במסך מלא'}</button></div></div></li>)}</ul>
    </Card>
    <Link to="/imports" className={buttonClasses('secondary')}>{english ? 'Back to data import' : 'חזרה לייבוא נתונים'}</Link>
    {selectedRequest && <SupportConversationDialog request={selectedRequest} staff={false} english={english} onClose={() => setSelectedRequestId(null)} />}
  </div>
}
