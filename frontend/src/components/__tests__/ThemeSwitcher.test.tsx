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
  it('toggles the dark class on the document when clicked', async () => {
    const user = userEvent.setup()
    renderSwitcher()
    const toggle = screen.getByRole('button', { name: 'שינוי מצב תצוגה' })

    await user.click(toggle)
    expect(document.documentElement.classList.contains('dark')).toBe(true)

    await user.click(toggle)
    expect(document.documentElement.classList.contains('dark')).toBe(false)
  })

  it('reflects the current theme via aria-pressed', async () => {
    const user = userEvent.setup()
    renderSwitcher()
    const toggle = screen.getByRole('button', { name: 'שינוי מצב תצוגה' })

    await user.click(toggle)
    expect(toggle).toHaveAttribute('aria-pressed', 'true')

    await user.click(toggle)
    expect(toggle).toHaveAttribute('aria-pressed', 'false')
  })
})
