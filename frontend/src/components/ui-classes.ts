// Class-name helpers shared by components (kept apart from ui.tsx so fast refresh stays component-only).

/** Joins class names, skipping falsy values. */
export function cx(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(' ')
}

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'subtle'
export type ButtonSize = 'sm' | 'md' | 'lg'

const BUTTON_BASE =
  'inline-flex shrink-0 items-center justify-center gap-2 rounded-lg font-medium whitespace-nowrap transition-[background-color,border-color,color,box-shadow,transform] duration-150 active:translate-y-px disabled:pointer-events-none disabled:opacity-50'

const BUTTON_VARIANTS: Record<ButtonVariant, string> = {
  primary:
    'bg-brand-600 text-white shadow-[inset_0_1px_0_rgb(255_255_255/0.12),0_1px_2px_rgb(8_36_31/0.2)] hover:bg-brand-700 dark:bg-brand-500 dark:text-brand-950 dark:hover:bg-brand-400',
  secondary:
    'border border-zinc-300 bg-white text-zinc-800 shadow-card hover:border-zinc-400 hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:hover:border-zinc-600 dark:hover:bg-zinc-800',
  ghost:
    'text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800 dark:hover:text-zinc-50',
  subtle:
    'bg-brand-50 text-brand-700 hover:bg-brand-100 dark:bg-brand-500/10 dark:text-brand-300 dark:hover:bg-brand-500/20',
  danger:
    'bg-danger-600 text-white shadow-[inset_0_1px_0_rgb(255_255_255/0.12)] hover:bg-danger-700 dark:bg-danger-600 dark:hover:bg-danger-500',
}

const BUTTON_SIZES: Record<ButtonSize, string> = {
  sm: 'h-8 px-3 text-xs',
  md: 'h-10 px-4 text-sm',
  lg: 'h-11 px-5 text-[0.9375rem]',
}

/** Shared button look, also usable on `Link`/`a` elements. */
export function buttonClasses(variant: ButtonVariant = 'primary', size: ButtonSize = 'md', extra?: string): string {
  return cx(BUTTON_BASE, BUTTON_VARIANTS[variant], BUTTON_SIZES[size], extra)
}

export const cardClasses =
  'rounded-xl border border-zinc-200/80 bg-white shadow-card dark:border-zinc-800 dark:bg-zinc-900'
