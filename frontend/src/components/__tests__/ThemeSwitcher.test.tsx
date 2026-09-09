import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { ThemeSwitcher } from '../ThemeSwitcher'
import { ThemeProvider } from '../../contexts/ThemeContext'
import { render, screen } from '../../test/test-utils'

function renderSwitcher() {
  return render(
    <ThemeProvider>
      <ThemeSwitcher />
    </ThemeProvider>,
  )
}

describe('ThemeSwitcher', () => {
  it('opens a menu with all three theme options', async () => {
    const user = userEvent.setup()
    renderSwitcher()
    await user.click(screen.getByRole('button', { name: 'שינוי מצב תצוגה' }))

    expect(screen.getByRole('option', { name: /בהיר/ })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: /כהה/ })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: /לפי המערכת/ })).toBeInTheDocument()
  })

  it('selecting dark mode applies the dark class to the document', async () => {
    const user = userEvent.setup()
    renderSwitcher()
    await user.click(screen.getByRole('button', { name: 'שינוי מצב תצוגה' }))
    await user.click(screen.getByTestId('theme-option-dark'))

    expect(document.documentElement.classList.contains('dark')).toBe(true)
  })
})
