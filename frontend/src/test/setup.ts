import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterAll, afterEach, beforeAll, beforeEach } from 'vitest'

import i18n, { DEFAULT_LANGUAGE, LANGUAGE_STORAGE_KEY } from '../i18n'
import { server } from './msw/server'

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

beforeEach(() => {
  window.localStorage.clear()
  if (i18n.language !== DEFAULT_LANGUAGE) {
    void i18n.changeLanguage(DEFAULT_LANGUAGE)
  }
})

afterEach(() => {
  cleanup()
  window.localStorage.removeItem(LANGUAGE_STORAGE_KEY)
})
