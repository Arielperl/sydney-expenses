import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { Layout } from './components/Layout'
import { AddSalePage } from './pages/AddSalePage'
import { AssistantPage } from './pages/AssistantPage'
import { DashboardPage } from './pages/DashboardPage'
import { ExceptionCenterPage } from './pages/ExceptionCenterPage'
import { ImportDocumentPage } from './pages/ImportDocumentPage'
import { ImportsPage } from './pages/ImportsPage'
import { SalesPage } from './pages/SalesPage'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<DashboardPage />} />
          <Route path="sales" element={<SalesPage />} />
          <Route path="add-sale" element={<AddSalePage />} />
          <Route path="import-document" element={<ImportDocumentPage />} />
          <Route path="exceptions" element={<ExceptionCenterPage />} />
          <Route path="imports" element={<ImportsPage />} />
          <Route path="assistant" element={<AssistantPage />} />

          {/* Old expense-oriented routes, kept as redirects to avoid broken navigation/bookmarks. */}
          <Route path="expenses" element={<Navigate to="/sales" replace />} />
          <Route path="add-expense" element={<Navigate to="/add-sale" replace />} />
          <Route path="upload-receipt" element={<Navigate to="/import-document" replace />} />
          <Route path="reconciliation" element={<Navigate to="/exceptions" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
