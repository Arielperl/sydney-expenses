export type WarningGroup = 'recovered' | 'review' | 'attention'

const REVIEW_SUFFIX = '_conflicting_sources'
const RECOVERED_SUFFIX = '_from_ocr'

/** Groups a warning code by what it's actually telling the user, so a long
 * flat list of codes doesn't read as one undifferentiated block of noise:
 * - "recovered": a value was filled in from receipt text the vision model
 *   itself missed — informational, not necessarily something to fix.
 * - "review": the vision model and the deterministic text parser disagreed —
 *   worth a second look before saving.
 * - "attention": nothing could be determined for this field at all. */
export function classifyWarning(code: string): WarningGroup {
  if (code.endsWith(REVIEW_SUFFIX)) return 'review'
  if (code.endsWith(RECOVERED_SUFFIX)) return 'recovered'
  return 'attention'
}

export function dedupeWarnings(warnings: string[]): string[] {
  return Array.from(new Set(warnings))
}

export function groupWarnings(warnings: string[]): Record<WarningGroup, string[]> {
  const deduped = dedupeWarnings(warnings)
  const groups: Record<WarningGroup, string[]> = { recovered: [], review: [], attention: [] }
  for (const code of deduped) {
    groups[classifyWarning(code)].push(code)
  }
  return groups
}
