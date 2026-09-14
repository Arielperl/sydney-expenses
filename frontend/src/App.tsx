import { lazy, Suspense } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { AuthProvider, RequireAuth } from './contexts/AuthContext'
import { AuthPage } from './pages/AuthPage'
import { HomePage } from './pages/HomePage'
import { Layout } from './components/Layout'
const AddSalePage = lazy(() => import('./pages/AddSalePage').then(module => ({ default: module.AddSalePage })))
const AssistantPage = lazy(() => import('./pages/AssistantPage').then(module => ({ default: module.AssistantPage })))
const DashboardPage = lazy(() => import('./pages/DashboardPage').then(module => ({ default: module.DashboardPage })))
const DemoSimulatorPage = lazy(() => import('./pages/DemoSimulatorPage').then(module => ({ default: module.DemoSimulatorPage })))
const ExceptionCenterPage = lazy(() => import('./pages/ExceptionCenterPage').then(module => ({ default: module.ExceptionCenterPage })))
const ImportDocumentPage = lazy(() => import('./pages/ImportDocumentPage').then(module => ({ default: module.ImportDocumentPage })))
const ImportsPage = lazy(() => import('./pages/ImportsPage').then(module => ({ default: module.ImportsPage })))
const SaleDetailsPage = lazy(() => import('./pages/SaleDetailsPage').then(module => ({ default: module.SaleDetailsPage })))
const SalesPage = lazy(() => import('./pages/SalesPage').then(module => ({ default: module.SalesPage })))

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
      <Suspense fallback={<div className="auth-state" dir="rtl" role="status">טוענים את סביבת העבודה…</div>}>
      <Routes>
        <Route index element={<HomePage />} />
        <Route path="login" element={<AuthPage key="login" mode="login" />} />
        <Route path="signup" element={<AuthPage key="signup" mode="signup" />} />
        <Route element={<RequireAuth />}>
        <Route element={<Layout />}>
          <Route path="app" element={<DashboardPage />} />
          <Route path="sales" element={<SalesPage />} />
          <Route path="sales/:id" element={<SaleDetailsPage />} />
          <Route path="add-sale" element={<AddSalePage />} />
          <Route path="import-document" element={<ImportDocumentPage />} />
          <Route path="exceptions" element={<ExceptionCenterPage />} />
          <Route path="imports" element={<ImportsPage />} />
          <Route path="demo" element={<DemoSimulatorPage />} />
          <Route path="assistant" element={<AssistantPage />} />

          {/* Old expense-oriented routes, kept as redirects to avoid broken navigation/bookmarks. */}
          <Route path="expenses" element={<Navigate to="/sales" replace />} />
          <Route path="add-expense" element={<Navigate to="/add-sale" replace />} />
          <Route path="upload-receipt" element={<Navigate to="/import-document" replace />} />
          <Route path="reconciliation" element={<Navigate to="/exceptions" replace />} />
        </Route>
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      </Suspense>
    </AuthProvider>
    </BrowserRouter>
  )
}

export default App
