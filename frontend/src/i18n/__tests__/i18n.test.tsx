import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { Layout } from '../../components/Layout'
import { renderWithProviders, screen, waitFor } from '../../test/test-utils'
import { LANGUAGE_STORAGE_KEY } from '../index'

function openLanguageMenu(user: ReturnType<typeof userEvent.setup>) {
  return user.click(screen.getByRole('button', { name: /שינוי שפה|Change language/ }))
}

describe('language / i18n', () => {
  it('defaults to Hebrew for a browser with no saved preference', () => {
    renderWithProviders(<Layout />)

    expect(screen.getByText('לוח בקרה')).toBeInTheDocument()
    expect(document.documentElement.lang).toBe('he')
    expect(document.documentElement.dir).toBe('rtl')
  })

  it('does not show both language choices permanently — only the trigger button', () => {
    renderWithProviders(<Layout />)

    expect(screen.queryByTestId('language-option-he')).not.toBeInTheDocument()
    expect(screen.queryByTestId('language-option-en')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'שינוי שפה' })).toBeInTheDocument()
  })

  it('opens the language menu on click, listing both choices', async () => {
    const user = userEvent.setup()
    renderWithProviders(<Layout />)

    await openLanguageMenu(user)

    expect(screen.getByRole('listbox')).toBeInTheDocument()
    expect(screen.getByTestId('language-option-he')).toBeInTheDocument()
    expect(screen.getByTestId('language-option-en')).toBeInTheDocument()
  })

  it('marks the currently selected language with aria-selected (checkmark)', async () => {
    const user = userEvent.setup()
    renderWithProviders(<Layout />)

    await openLanguageMenu(user)

    expect(screen.getByTestId('language-option-he')).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByTestId('language-option-en')).toHaveAttribute('aria-selected', 'false')
  })

  it('switches content and document direction when English is selected', async () => {
    const user = userEvent.setup()
    renderWithProviders(<Layout />)

    await openLanguageMenu(user)
    await user.click(screen.getByTestId('language-option-en'))

    expect(screen.getByText('Dashboard')).toBeInTheDocument()
    expect(screen.queryByText('לוח בקרה')).not.toBeInTheDocument()
    expect(document.documentElement.lang).toBe('en')
    expect(document.documentElement.dir).toBe('ltr')
  })

  it('closes the menu after selecting a language', async () => {
    const user = userEvent.setup()
    renderWithProviders(<Layout />)

    await openLanguageMenu(user)
    await user.click(screen.getByTestId('language-option-en'))

    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  })

  it('persists the selected language to localStorage', async () => {
    const user = userEvent.setup()
    renderWithProviders(<Layout />)

    await openLanguageMenu(user)
    await user.click(screen.getByTestId('language-option-en'))

    expect(window.localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBe('en')
  })

  it('switching back to Hebrew restores RTL and Hebrew content', async () => {
    const user = userEvent.setup()
    renderWithProviders(<Layout />)

    await openLanguageMenu(user)
    await user.click(screen.getByTestId('language-option-en'))
    await openLanguageMenu(user)
    await user.click(screen.getByTestId('language-option-he'))

    expect(screen.getByText('לוח בקרה')).toBeInTheDocument()
    expect(document.documentElement.dir).toBe('rtl')
    expect(window.localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBe('he')
  })

  it('closes the menu when pressing Escape, returning focus to the trigger', async () => {
    const user = userEvent.setup()
    renderWithProviders(<Layout />)

    await openLanguageMenu(user)
    expect(screen.getByRole('listbox')).toBeInTheDocument()

    await user.keyboard('{Escape}')

    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'שינוי שפה' })).toHaveFocus()
  })

  it('closes the menu when clicking outside it', async () => {
    const user = userEvent.setup()
    renderWithProviders(<Layout />)

    await openLanguageMenu(user)
    expect(screen.getByRole('listbox')).toBeInTheDocument()

    await user.click(document.body)

    await waitFor(() => expect(screen.queryByRole('listbox')).not.toBeInTheDocument())
  })

  it('supports arrow-key navigation between the two options', async () => {
    const user = userEvent.setup()
    renderWithProviders(<Layout />)

    await openLanguageMenu(user)
    // The currently-selected option (Hebrew) receives focus when the menu opens.
    expect(screen.getByTestId('language-option-he')).toHaveFocus()

    await user.keyboard('{ArrowDown}')
    expect(screen.getByTestId('language-option-en')).toHaveFocus()

    await user.keyboard('{Enter}')
    expect(document.documentElement.lang).toBe('en')
  })
})
