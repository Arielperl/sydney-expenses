import { useState, type FormEvent } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { apiClient } from '../services/apiClient'
import { ProductPreview, PublicBrand } from './HomePage'

export function CreateBusinessPage() {
  const { reload, logout } = useAuth()
  const [name, setName] = useState('')
  const [number, setNumber] = useState('')
  const [providers, setProviders] = useState<Array<'grow' | 'cardcom'>>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function submit(e: FormEvent) {
    e.preventDefault(); setBusy(true); setError('')
    try {
      await apiClient.post('/businesses', {
        name: name.trim(),
        business_number: number.trim() || null,
        payment_providers: providers,
      })
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
      <fieldset>
        <legend>עם אילו חברות סליקה העסק עובד?</legend>
        <p className="auth-hint">בחרו את כל החברות הרלוונטיות. לאחר יצירת העסק, הוספת חברה נוספת מתבצעת דרך התמיכה.</p>
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          {([['grow', 'Grow'], ['cardcom', 'Cardcom']] as const).map(([value, label]) => (
            <label key={value} className="provider-option">
              <input
                type="checkbox"
                checked={providers.includes(value)}
                onChange={(event) => setProviders((current) => event.target.checked
                  ? [...current, value]
                  : current.filter((provider) => provider !== value))}
              />
              <span>{label}</span>
            </label>
          ))}
        </div>
        <p className="auth-hint">אם אינכם עובדים כרגע עם חברה נתמכת, אפשר להמשיך ללא בחירה ולהשתמש בייבוא CSV.</p>
      </fieldset>
      <p className="auth-note mt-5">הגרסה הנוכחית מותאמת לישראל: מטבע תצוגה שקל ואזור זמן ירושלים. טיפול המע״מ נבחר לכל מכירה.</p>
      {error && <p className="auth-message error" role="alert">{error}</p>}
      <button className="public-button" disabled={busy}>{busy ? 'יוצרים את העסק…' : 'יצירת העסק וכניסה למערכת'}</button>
      <button type="button" className="auth-forgot" onClick={() => void logout().catch(() => setError('ההתנתקות נכשלה. נסו שוב.'))}>התנתקות</button>
    </form><p className="auth-note">מנהל הכנסות · מבית Sydney</p></section><aside className="auth-art"><h2>העסק שלכם.<br/>הנתונים שלכם.</h2><p>המכירות והמסמכים זמינים רק לחברי העסק המורשים.</p><ProductPreview/><span className="preview-caption">תצוגה להמחשה בלבד</span></aside></div>
}
