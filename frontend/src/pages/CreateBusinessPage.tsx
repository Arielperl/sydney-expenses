import { useState, type FormEvent } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { apiClient } from '../services/apiClient'
import { PublicBrand } from './HomePage'

export function CreateBusinessPage() {
  const { reload, logout } = useAuth()
  const [name, setName] = useState('')
  const [number, setNumber] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function submit(e: FormEvent) {
    e.preventDefault(); setBusy(true); setError('')
    try {
      await apiClient.post('/businesses', { name: name.trim(), business_number: number.trim() || null })
      await reload()
    } catch (e) {
      const status = (e as { response?: { status?: number } }).response?.status
      if (status === 409) await reload()
      else setError(status === 403 ? 'יש לאמת את כתובת האימייל לפני יצירת עסק.' : 'לא הצלחנו ליצור את העסק. נסו שוב.')
    } finally { setBusy(false) }
  }
  return <div className="auth-shell" dir="rtl"><section className="auth-form-side"><PublicBrand/>
    <form className="auth-form" onSubmit={submit}>
      <h1>נכיר את העסק שלכם</h1><p>ניצור סביבת עבודה פרטית למכירות ולנתונים של העסק.</p>
      <label htmlFor="business-name">שם העסק</label><input id="business-name" required minLength={2} maxLength={100} value={name} onChange={e => setName(e.target.value)}/>
      <label htmlFor="business-number">מספר עוסק (אופציונלי)</label><input id="business-number" maxLength={30} value={number} onChange={e => setNumber(e.target.value)}/>
      <label htmlFor="business-country">מדינה</label><input id="business-country" value="ישראל" readOnly/>
      <p className="auth-note">הגרסה הנוכחית מותאמת לישראל: מטבע תצוגה שקל ואזור זמן ירושלים. טיפול המע״מ נבחר לכל מכירה.</p>
      {error && <p className="auth-message error" role="alert">{error}</p>}
      <button className="public-button" disabled={busy}>{busy ? 'יוצרים את העסק…' : 'יצירת העסק וכניסה למערכת'}</button>
      <button type="button" className="auth-forgot" onClick={() => void logout().catch(() => setError('ההתנתקות נכשלה. נסו שוב.'))}>התנתקות</button>
    </form><p className="auth-note">מנהל הכנסות · מבית Sydney</p></section><aside className="auth-art"><h2>העסק שלכם.<br/>הנתונים שלכם.</h2><p>המכירות והמסמכים זמינים רק לחברי העסק המורשים.</p></aside></div>
}
