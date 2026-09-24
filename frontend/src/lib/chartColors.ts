import type { ResolvedTheme } from '../contexts/ThemeContext'

export interface ChartColors {
  grid: string
  tick: string
  axisLabel: string
  tooltipCursor: string
  series: string
  seriesFill: string
}

const LIGHT_CHART_COLORS: ChartColors = {
  grid: '#e1e6e3',
  tick: '#69736f',
  axisLabel: '#3b4441',
  tooltipCursor: '#cbd3cf',
  series: '#17745f',
  seriesFill: '#26957a',
}

const DARK_CHART_COLORS: ChartColors = {
  grid: '#252c2a',
  tick: '#98a29e',
  axisLabel: '#e1e6e3',
  tooltipCursor: '#3b4441',
  series: '#7ccdb5',
  seriesFill: '#47b395',
}

export function getChartColors(theme: ResolvedTheme): ChartColors {
  return theme === 'dark' ? DARK_CHART_COLORS : LIGHT_CHART_COLORS
}
