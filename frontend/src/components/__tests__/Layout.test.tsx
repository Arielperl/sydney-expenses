import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import { Layout } from '../Layout'
import { ThemeProvider } from '../../contexts/ThemeContext'
import { render, screen, within } from '../../test/test-utils'

function renderLayout() {
  return render(
    <ThemeProvider>
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<div>Dashboard content</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </ThemeProvider>,
  )
}

describe('Layout', () => {
  it('renders all nav links and the routed page content', () => {
    renderLayout()
    expect(screen.getByRole('link', { name: /לוח בקרה/ })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /עוזר AI/ })).toBeInTheDocument()
    expect(screen.getByText('Dashboard content')).toBeInTheDocument()
  })

  it('shows a 5-item primary nav without Upload Receipt or Add Expense', () => {
    renderLayout()
    const nav = screen.getByRole('navigation', { name: 'ניווט ראשי' })
    expect(within(nav).getAllByRole('link')).toHaveLength(5)
    expect(within(nav).queryByRole('link', { name: /העלאת קבלה/ })).not.toBeInTheDocument()
    expect(within(nav).queryByRole('link', { name: /הוספת הוצאה/ })).not.toBeInTheDocument()
  })

  it('opens the mobile drawer and closes it on Escape', async () => {
    const user = userEvent.setup()
    renderLayout()

    expect(screen.getAllByRole('link', { name: /הוצאות/ })).toHaveLength(1)

    await user.click(screen.getByRole('button', { name: 'פתיחת תפריט' }))
    expect(screen.getAllByRole('link', { name: /הוצאות/ })).toHaveLength(2)

    await user.keyboard('{Escape}')
    expect(screen.getAllByRole('link', { name: /הוצאות/ })).toHaveLength(1)
  })
})
