import { describe, expect, it } from 'vitest'

import { getChartColors } from '../chartColors'

describe('getChartColors', () => {
  it('returns light-mode colors for the light theme', () => {
    const colors = getChartColors('light')
    expect(colors.grid).toBe('#e7e5e4')
    expect(colors.tick).toBe('#78716c')
  })

  it('returns dark-mode colors for the dark theme', () => {
    const colors = getChartColors('dark')
    expect(colors.grid).toBe('#44403c')
    expect(colors.tick).toBe('#a8a29e')
  })
})
