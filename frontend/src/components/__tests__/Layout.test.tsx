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

  it('shows a 6-item primary nav: dashboard, sales, exceptions, imports, demo area, assistant', () => {
    renderLayout()
    const nav = screen.getByRole('navigation', { name: 'ניווט ראשי' })
    expect(within(nav).getAllByRole('link')).toHaveLength(6)
    expect(within(nav).getByRole('link', { name: /מכירות/ })).toBeInTheDocument()
    expect(within(nav).getByRole('link', { name: /מרכז חריגים/ })).toBeInTheDocument()
    expect(within(nav).getByRole('link', { name: /אזור הדגמה/ })).toBeInTheDocument()
  })

  it('opens the mobile drawer and closes it on Escape', async () => {
    const user = userEvent.setup()
    renderLayout()

    expect(screen.getAllByRole('link', { name: /מכירות/ })).toHaveLength(1)

    await user.click(screen.getByRole('button', { name: 'פתיחת תפריט' }))
    expect(screen.getAllByRole('link', { name: /מכירות/ })).toHaveLength(2)

    await user.keyboard('{Escape}')
    expect(screen.getAllByRole('link', { name: /מכירות/ })).toHaveLength(1)
  })
})
