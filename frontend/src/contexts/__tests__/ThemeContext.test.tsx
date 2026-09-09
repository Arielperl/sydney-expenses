import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ThemeProvider, useTheme } from '../ThemeContext'

function mockMatchMedia(matches: boolean) {
  const listeners = new Set<() => void>()
  const mediaQueryList = {
    matches,
    media: '(prefers-color-scheme: dark)',
    addEventListener: (_event: string, listener: () => void) => listeners.add(listener),
    removeEventListener: (_event: string, listener: () => void) => listeners.delete(listener),
  }
  window.matchMedia = vi.fn().mockReturnValue(mediaQueryList) as unknown as typeof window.matchMedia
  return {
    fireChange: (newMatches: boolean) => {
      mediaQueryList.matches = newMatches
      listeners.forEach((listener) => listener())
    },
  }
}

describe('ThemeProvider', () => {
  beforeEach(() => {
    window.localStorage.clear()
    document.documentElement.classList.remove('dark')
  })

  afterEach(() => {
    document.documentElement.classList.remove('dark')
  })

  it('defaults to system mode and resolves to the OS preference', () => {
    mockMatchMedia(true)
    const { result } = renderHook(() => useTheme(), { wrapper: ThemeProvider })
    expect(result.current.mode).toBe('system')
    expect(result.current.resolvedTheme).toBe('dark')
    expect(document.documentElement.classList.contains('dark')).toBe(true)
  })

  it('reads a previously stored mode from localStorage', () => {
    mockMatchMedia(false)
    window.localStorage.setItem('receiptly-theme', 'dark')
    const { result } = renderHook(() => useTheme(), { wrapper: ThemeProvider })
    expect(result.current.mode).toBe('dark')
    expect(result.current.resolvedTheme).toBe('dark')
  })

  it('setMode persists the choice and updates the document class', () => {
    mockMatchMedia(false)
    const { result } = renderHook(() => useTheme(), { wrapper: ThemeProvider })

    act(() => result.current.setMode('dark'))
    expect(window.localStorage.getItem('receiptly-theme')).toBe('dark')
    expect(result.current.resolvedTheme).toBe('dark')
    expect(document.documentElement.classList.contains('dark')).toBe(true)

    act(() => result.current.setMode('light'))
    expect(document.documentElement.classList.contains('dark')).toBe(false)
  })

  it('tracks OS preference changes while in system mode', () => {
    const media = mockMatchMedia(false)
    const { result } = renderHook(() => useTheme(), { wrapper: ThemeProvider })
    expect(result.current.resolvedTheme).toBe('light')

    act(() => media.fireChange(true))
    expect(result.current.resolvedTheme).toBe('dark')
  })
})
