import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { renderWithProviders, screen } from '../../test/test-utils'
import { HomePage } from '../HomePage'

describe('Home page demo video', () => {
  it('loads the video only after the visitor asks to watch it and closes on Escape', async () => {
    const user = userEvent.setup()
    renderWithProviders(<HomePage />)

    expect(screen.queryByRole('dialog', { name: 'המערכת ב־30 שניות' })).not.toBeInTheDocument()

    const trigger = screen.getByRole('button', { name: /צפו בהדגמה/ })
    await user.click(trigger)

    expect(screen.getByRole('dialog', { name: 'המערכת ב־30 שניות' })).toBeInTheDocument()
    expect(screen.getByLabelText('סרטון הדגמה של מנהל ההכנסות Sydney')).toHaveAttribute('preload', 'metadata')

    await user.keyboard('{Escape}')

    expect(screen.queryByRole('dialog', { name: 'המערכת ב־30 שניות' })).not.toBeInTheDocument()
    expect(trigger).toHaveFocus()
  })
})
