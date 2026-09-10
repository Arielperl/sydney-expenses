import { BrowserRouter, Route, Routes } from 'react-router-dom'

import { Layout } from './components/Layout'
import { AddExpensePage } from './pages/AddExpensePage'
import { AssistantPage } from './pages/AssistantPage'
import { DashboardPage } from './pages/DashboardPage'
import { ExpensesPage } from './pages/ExpensesPage'
import { ImportsPage } from './pages/ImportsPage'
import { ReconciliationInboxPage } from './pages/ReconciliationInboxPage'
import { UploadReceiptPage } from './pages/UploadReceiptPage'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<DashboardPage />} />
          <Route path="expenses" element={<ExpensesPage />} />
          <Route path="add-expense" element={<AddExpensePage />} />
          <Route path="upload-receipt" element={<UploadReceiptPage />} />
          <Route path="reconciliation" element={<ReconciliationInboxPage />} />
          <Route path="imports" element={<ImportsPage />} />
          <Route path="assistant" element={<AssistantPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
