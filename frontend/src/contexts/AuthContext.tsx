import { createContext, useContext, useEffect, useState, useCallback, useRef, type ReactNode } from 'react'
import { Navigate, Outlet, Link, useLocation } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { apiClient } from '../services/apiClient'
import '../pages/PublicPages.css'
import { CreateBusinessPage } from '../pages/CreateBusinessPage'

type User = { id: string; email: string; name: string; has_workspace: boolean; business_name?: string; role?: string; system_role: 'user' | 'support' | 'admin' | 'superadmin' }
type AuthState = { user: User | null; loading: boolean; error: boolean; reload: () => Promise<void>; logout: () => Promise<void>; setUser: (user: User | null) => void }
const AuthContext = createContext<AuthState | null>(null)
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, updateUser] = useState<User | null>(null)
  const generation = useRef(0)
  const setUser = useCallback((next: User | null) => { generation.current += 1; updateUser(next) }, [])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const queryClient = useQueryClient()
  const reload = useCallback(async () => {
    const requestGeneration = generation.current
    setError(false)
    try { const { data } = await apiClient.get('/auth/session'); if (generation.current === requestGeneration) updateUser(data.user) }
    catch (e) { if (generation.current !== requestGeneration) return; updateUser(null); const status = (e as { response?: { status: number } }).response?.status; setError(status !== 401) }
    finally { setLoading(false) }
  }, [])
  useEffect(() => { void reload() }, [reload])
  useEffect(() => {
    const handleExpired = () => { queryClient.clear(); setUser(null) }
    window.addEventListener('sydney:session-expired', handleExpired)
    return () => window.removeEventListener('sydney:session-expired', handleExpired)
  }, [queryClient, setUser])
  const logout = async () => { await apiClient.post('/auth/logout'); queryClient.clear(); setUser(null) }
  return <AuthContext.Provider value={{ user, loading, error, reload, logout, setUser }}>{children}</AuthContext.Provider>
}
export function useAuth() { const value = useContext(AuthContext); if (!value) throw new Error('AuthProvider required'); return value }
export function RequireAuth() {
  const { user, loading, error, reload } = useAuth()
  const location = useLocation()
  if (loading) return <div className="auth-state" dir="rtl" role="status">בודקים את מצב ההתחברות…</div>
  if (error) return <div className="auth-state" dir="rtl"><h1>לא הצלחנו להתחבר לשירות</h1><p>ייתכן שיש תקלה זמנית בחיבור. נסו שוב בעוד רגע.</p><button type="button" onClick={() => void reload()}>ניסיון נוסף</button><Link to="/">חזרה לדף הבית</Link></div>
  if (!user) return <Navigate to="/login" state={{ from: location.pathname + location.search + location.hash }} replace/>
  if (user.system_role === 'support' || user.system_role === 'admin') return <Navigate to="/support" replace />
  if (!user.has_workspace) return <CreateBusinessPage/>
  return <Outlet/>
}

export function RequireSupport() {
  const { user, loading, error, reload } = useAuth()
  if (loading) return <div className="auth-state" dir="rtl" role="status">בודקים הרשאות…</div>
  if (error) return <div className="auth-state" dir="rtl"><p>לא ניתן לבדוק הרשאות כרגע.</p><button onClick={() => void reload()}>ניסיון נוסף</button></div>
  if (!user) return <Navigate to="/support/login" replace />
  if (!['support', 'admin', 'superadmin'].includes(user.system_role)) return <div className="auth-state" dir="rtl"><h1>אין גישה לממשק התמיכה</h1><Link to="/app">חזרה למערכת</Link></div>
  return <Outlet />
}
