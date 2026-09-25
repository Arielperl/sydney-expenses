import { useState, useEffect, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { ArrowLeft, Eye, EyeOff } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { PublicBrand, ProductPreview } from './HomePage'
import { useAuth } from '../contexts/AuthContext'
import { apiClient, toApiError } from '../services/apiClient'
import './PublicPages.css'

export function AuthPage({ mode }: { mode: 'login' | 'signup' }) {
 const signup = mode === 'signup'
 const { user, setUser } = useAuth()
 const navigate = useNavigate()
 const location = useLocation()
 const queryClient = useQueryClient()
 const [email, setEmail] = useState('')
 const [password, setPassword] = useState('')
 const [name, setName] = useState('')
 const [showPassword, setShowPassword] = useState(false)
 const [busy, setBusy] = useState(false)
 const [error, setError] = useState('')
 const [confirmation, setConfirmation] = useState(false)
 useEffect(() => {
  // Email confirmation can return implicit credentials; password login owns this flow.
  const params = new URLSearchParams(window.location.hash.slice(1))
  if (params.has('access_token') || params.has('error')) {
   if (params.has('error')) setError('קישור האימות אינו תקף או פג תוקף. נסו להתחבר או להירשם מחדש.')
   window.history.replaceState(window.history.state, '', window.location.pathname + window.location.search)
  }
 }, [])
 const requestedPath = location.state?.from
 const target = typeof requestedPath === 'string' && requestedPath.startsWith('/') && !requestedPath.startsWith('//') && !requestedPath.includes('\\') && requestedPath !== '/' && !requestedPath.startsWith('/login') && !requestedPath.startsWith('/signup') ? requestedPath : '/app'
 if (user) return <Navigate to={user.system_role === 'support' || user.system_role === 'admin' ? '/support' : target} replace/>
 async function submit(event: FormEvent) {
  event.preventDefault(); setError(''); setBusy(true)
  try {
   const { data } = await apiClient.post(`/auth/${mode}`, { email: email.trim(), password, name: name.trim() })
   if (data.confirmation_required) { setConfirmation(true); setPassword('') }
   else { queryClient.clear(); setUser(data.user); navigate(data.user.system_role === 'support' || data.user.system_role === 'admin' ? '/support' : target, { replace: true }) }
  } catch (e) { setError(toApiError(e).message) }
  finally { setBusy(false) }
 }
 return <div className="auth-shell" dir="rtl"><div className="auth-form-side"><PublicBrand/><div className="auth-form"><span className="eyebrow">{signup ? 'היכרות קטנה. התחלה חדשה.' : 'טוב שחזרתם.'}</span><h1>{signup ? 'העסק שלכם. במקום אחד.' : 'מתחברים לתמונה המלאה.'}</h1><p>{signup ? 'פותחים חשבון ומתחילים לעשות סדר בהכנסות.' : 'הזינו את פרטי החשבון כדי להמשיך לסביבת העבודה.'}</p>
 {confirmation ? <><div className="auth-message" role="status">אם הכתובת יכולה להירשם, נשלח אליה קישור לאימות. בדקו גם את תיקיית הספאם, אשרו את האימייל ואז חזרו להתחבר.</div><p dir="ltr">{email}</p><Link to="/login" className="public-button">מעבר להתחברות <ArrowLeft size={18}/></Link></> : <form onSubmit={submit}>
{signup && <label htmlFor="full-name">השם שלכם<input id="full-name" autoComplete="name" required maxLength={100} value={name} onChange={e=>setName(e.target.value)}/></label>}
<label htmlFor="email">כתובת אימייל<input id="email" type="email" dir="ltr" autoComplete="email" required maxLength={254} value={email} onChange={e=>setEmail(e.target.value)}/></label>
<label htmlFor="password">סיסמה<div className="password-wrap"><input id="password" type={showPassword ? 'text' : 'password'} dir="ltr" required minLength={signup ? 8 : 1} maxLength={128} autoComplete={signup ? 'new-password' : 'current-password'} value={password} onChange={e=>setPassword(e.target.value)}/><button type="button" onClick={()=>setShowPassword(!showPassword)} aria-label={showPassword ? 'הסתרת סיסמה' : 'הצגת סיסמה'}>{showPassword ? <EyeOff size={19}/> : <Eye size={19}/>}</button></div></label>
 {error && <div className="auth-message error" role="alert">{error}</div>}
 <button className="public-button" disabled={busy} type="submit">{busy ? 'רק רגע…' : signup ? 'יצירת חשבון' : 'כניסה למערכת'}{!busy && <ArrowLeft size={18}/>}</button>
 {signup && <p className="auth-note" style={{marginTop:16}}>המוצר בשלב ההרצה. גישה לנתוני עסק נפתחת לאחר שיוך החשבון לעסק.</p>}
 </form>}
 <div className="auth-bottom">{signup ? 'כבר יש לכם חשבון?' : 'עדיין אין לכם חשבון?'}{' '}<Link state={location.state} to={signup ? '/login' : '/signup'}>{signup ? 'מתחברים כאן' : 'פותחים חשבון'}</Link></div></div><span className="auth-note">מנהל הכנסות · מבית Sydney</span></div><aside className="auth-art"><h2>פחות מספרים מפוזרים.<br/>יותר שקט בראש.</h2><p>כל המכירות, התקבולים והחריגים של העסק — בתמונה אחת ברורה.</p><ProductPreview/><span className="preview-caption">תצוגה להמחשה בלבד</span></aside></div>
}
