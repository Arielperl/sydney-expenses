const PALETTE = [
  '#2563eb',
  '#059669',
  '#d97706',
  '#dc2626',
  '#7c3aed',
  '#0891b2',
  '#db2777',
  '#65a30d',
  '#4f46e5',
  '#64748b',
]

const CATEGORY_ORDER = [
  'groceries',
  'dining',
  'transport',
  'utilities',
  'health',
  'shopping',
  'entertainment',
  'travel',
  'housing',
  'other',
]

export function colorForCategory(category: string): string {
  const index = CATEGORY_ORDER.indexOf(category)
  return PALETTE[index === -1 ? PALETTE.length - 1 : index]
}
