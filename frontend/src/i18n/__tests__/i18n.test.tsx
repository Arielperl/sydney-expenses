import { screen, fireEvent } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { Layout } from '../../components/Layout'
import { renderWithProviders } from '../../test/test-utils'
import { LANGUAGE_STORAGE_KEY } from '../index'

describe('language / i18n', () => {
  it('defaults to Hebrew for a browser with no saved preference', () => {
    renderWithProviders(<Layout />)

    expect(screen.getByText('לוח בקרה')).toBeInTheDocument()
    expect(document.documentElement.lang).toBe('he')
    expect(document.documentElement.dir).toBe('rtl')
  })

  it('switches content and document direction when English is selected', () => {
    renderWithProviders(<Layout />)

    fireEvent.click(screen.getByTestId('language-switch-en'))

    expect(screen.getByText('Dashboard')).toBeInTheDocument()
    expect(screen.queryByText('לוח בקרה')).not.toBeInTheDocument()
    expect(document.documentElement.lang).toBe('en')
    expect(document.documentElement.dir).toBe('ltr')
  })

  it('persists the selected language to localStorage', () => {
    renderWithProviders(<Layout />)

    fireEvent.click(screen.getByTestId('language-switch-en'))

    expect(window.localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBe('en')
  })

  it('switching back to Hebrew restores RTL and Hebrew content', () => {
    renderWithProviders(<Layout />)

    fireEvent.click(screen.getByTestId('language-switch-en'))
    fireEvent.click(screen.getByTestId('language-switch-he'))

    expect(screen.getByText('לוח בקרה')).toBeInTheDocument()
    expect(document.documentElement.dir).toBe('rtl')
    expect(window.localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBe('he')
  })
})
