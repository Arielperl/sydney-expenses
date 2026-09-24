import { lazy, Suspense, useEffect } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { AuthProvider, RequireAuth, RequireSupport } from './contexts/AuthContext'
import { AuthPage } from './pages/AuthPage'
import { HomePage } from './pages/HomePage'
import { Layout } from './components/Layout'
const AddSalePage = lazy(() => import('./pages/AddSalePage').then(module => ({ default: module.AddSalePage })))
const AssistantPage = lazy(() => import('./pages/AssistantPage').then(module => ({ default: module.AssistantPage })))
const DashboardPage = lazy(() => import('./pages/DashboardPage').then(module => ({ default: module.DashboardPage })))
const ExceptionCenterPage = lazy(() => import('./pages/ExceptionCenterPage').then(module => ({ default: module.ExceptionCenterPage })))
const ImportDocumentPage = lazy(() => import('./pages/ImportDocumentPage').then(module => ({ default: module.ImportDocumentPage })))
const ImportsPage = lazy(() => import('./pages/ImportsPage').then(module => ({ default: module.ImportsPage })))
const SaleDetailsPage = lazy(() => import('./pages/SaleDetailsPage').then(module => ({ default: module.SaleDetailsPage })))
const SalesPage = lazy(() => import('./pages/SalesPage').then(module => ({ default: module.SalesPage })))
const SupportRequestPage = lazy(() => import('./pages/SupportRequestPage').then(module => ({ default: module.SupportRequestPage })))
const SupportPortalPage = lazy(() => import('./pages/SupportPortalPage').then(module => ({ default: module.SupportPortalPage })))
const SupportLoginPage = lazy(() => import('./pages/SupportLoginPage').then(module => ({ default: module.SupportLoginPage })))

function SupportDomainRedirect() {
  useEffect(() => { window.location.replace(`https://support.sydneyexpenses.com${window.location.pathname}${window.location.search}`) }, [])
  return <div className="auth-state" dir="rtl" role="status">מעבירים לממשק התמיכה…</div>
}

function App() {
  const isSupportHost = import.meta.env.PROD && window.location.hostname === 'support.sydneyexpenses.com'
  const isStaffPath = window.location.pathname === '/support' || window.location.pathname === '/support/login'
  return (
    <BrowserRouter>
      <AuthProvider>
      <Suspense fallback={<div className="auth-state" dir="rtl" role="status">טוענים את סביבת העבודה…</div>}>
      {isSupportHost ? <Routes>
        <Route path="support/login" element={<SupportLoginPage />} />
        <Route element={<RequireSupport />}><Route path="support" element={<SupportPortalPage />} /></Route>
        <Route path="*" element={<Navigate to="/support" replace />} />
      </Routes> : isStaffPath && import.meta.env.PROD ? <SupportDomainRedirect /> :
      <Routes>
        <Route index element={<HomePage />} />
        <Route path="login" element={<AuthPage key="login" mode="login" />} />
        <Route path="signup" element={<AuthPage key="signup" mode="signup" />} />
        {!import.meta.env.PROD && <Route path="support/login" element={<SupportLoginPage />} />}
        {!import.meta.env.PROD && <Route element={<RequireSupport />}><Route path="support" element={<SupportPortalPage />} /></Route>}
        <Route element={<RequireAuth />}>
        <Route element={<Layout />}>
          <Route path="app" element={<DashboardPage />} />
          <Route path="sales" element={<SalesPage />} />
          <Route path="sales/:id" element={<SaleDetailsPage />} />
          <Route path="add-sale" element={<AddSalePage />} />
          <Route path="import-document" element={<ImportDocumentPage />} />
          <Route path="exceptions" element={<ExceptionCenterPage />} />
          <Route path="imports" element={<ImportsPage />} />
          <Route path="assistant" element={<AssistantPage />} />
          <Route path="support/request" element={<SupportRequestPage />} />
          <Route path="admin" element={<Navigate to="/app" replace />} />

          {/* Old expense-oriented routes, kept as redirects to avoid broken navigation/bookmarks. */}
          <Route path="expenses" element={<Navigate to="/sales" replace />} />
          <Route path="add-expense" element={<Navigate to="/add-sale" replace />} />
          <Route path="upload-receipt" element={<Navigate to="/import-document" replace />} />
          <Route path="reconciliation" element={<Navigate to="/exceptions" replace />} />
        </Route>
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      }
      </Suspense>
    </AuthProvider>
    </BrowserRouter>
  )
}

export default App
