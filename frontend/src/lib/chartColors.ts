import type { ResolvedTheme } from '../contexts/ThemeContext'

export interface ChartColors {
  grid: string
  tick: string
  axisLabel: string
  tooltipCursor: string
}

const LIGHT_CHART_COLORS: ChartColors = {
  grid: '#e7e5e4',
  tick: '#78716c',
  axisLabel: '#44403c',
  tooltipCursor: '#f5f5f4',
}

const DARK_CHART_COLORS: ChartColors = {
  grid: '#44403c',
  tick: '#a8a29e',
  axisLabel: '#e7e5e4',
  tooltipCursor: '#292524',
}

export function getChartColors(theme: ResolvedTheme): ChartColors {
  return theme === 'dark' ? DARK_CHART_COLORS : LIGHT_CHART_COLORS
}
