import { describe, expect, it } from 'vitest'

import { getChartColors } from '../chartColors'

describe('getChartColors', () => {
  it('returns light-mode colors for the light theme', () => {
    const colors = getChartColors('light')
    expect(colors.grid).toBe('#e1e6e3')
    expect(colors.tick).toBe('#69736f')
    expect(colors.series).toBe('#17745f')
  })

  it('returns dark-mode colors for the dark theme', () => {
    const colors = getChartColors('dark')
    expect(colors.grid).toBe('#252c2a')
    expect(colors.tick).toBe('#98a29e')
    expect(colors.series).toBe('#7ccdb5')
  })
})
