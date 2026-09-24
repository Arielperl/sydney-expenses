import type { ComponentPropsWithoutRef, ReactNode } from 'react'

import { buttonClasses, cardClasses, cx, type ButtonSize, type ButtonVariant } from './ui-classes'

export function Button({
  variant = 'primary',
  size = 'md',
  className,
  type = 'button',
  ...props
}: ComponentPropsWithoutRef<'button'> & { variant?: ButtonVariant; size?: ButtonSize }) {
  return <button type={type} className={buttonClasses(variant, size, className)} {...props} />
}

export function Card({ className, children, as: Tag = 'section', ...props }: ComponentPropsWithoutRef<'section'> & { as?: 'section' | 'div' | 'article' }) {
  return (
    <Tag className={cx(cardClasses, className)} {...props}>
      {children}
    </Tag>
  )
}

/** Title row for a card: heading, optional one-line description and actions. */
export function CardHeader({
  title,
  description,
  actions,
  id,
  className,
}: {
  title: ReactNode
  description?: ReactNode
  actions?: ReactNode
  id?: string
  className?: string
}) {
  return (
    <div className={cx('flex flex-wrap items-start justify-between gap-x-4 gap-y-2 px-5 pt-5', className)}>
      <div className="min-w-0">
        <h2 id={id} className="text-[0.9375rem] font-semibold text-zinc-900 dark:text-zinc-50">
          {title}
        </h2>
        {description && <p className="mt-0.5 text-sm text-zinc-500 dark:text-zinc-400">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}

/** Consistent page title block used at the top of every authenticated screen. */
export function PageHeader({
  title,
  description,
  actions,
  eyebrow,
}: {
  title: ReactNode
  description?: ReactNode
  actions?: ReactNode
  eyebrow?: ReactNode
}) {
  return (
    <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        {eyebrow && <div className="mb-1.5 text-xs font-medium text-brand-700 dark:text-brand-300">{eyebrow}</div>}
        <h1 className="text-[1.625rem] leading-tight font-semibold tracking-[-0.015em] text-zinc-900 dark:text-zinc-50">
          {title}
        </h1>
        {description && (
          <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-zinc-500 dark:text-zinc-400">{description}</p>
        )}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  )
}

export type BadgeTone = 'neutral' | 'brand' | 'success' | 'warning' | 'danger' | 'info'

const BADGE_TONES: Record<BadgeTone, { chip: string; dot: string }> = {
  neutral: { chip: 'bg-zinc-100 text-zinc-700 ring-zinc-200 dark:bg-zinc-800 dark:text-zinc-300 dark:ring-zinc-700', dot: 'bg-zinc-400' },
  brand: { chip: 'bg-brand-50 text-brand-800 ring-brand-200 dark:bg-brand-500/10 dark:text-brand-200 dark:ring-brand-500/25', dot: 'bg-brand-500' },
  success: { chip: 'bg-success-50 text-success-700 ring-success-500/20 dark:bg-success-500/10 dark:text-success-500 dark:ring-success-500/25', dot: 'bg-success-500' },
  warning: { chip: 'bg-amber-50 text-amber-800 ring-amber-600/20 dark:bg-amber-500/10 dark:text-amber-300 dark:ring-amber-500/25', dot: 'bg-amber-500' },
  danger: { chip: 'bg-danger-50 text-danger-700 ring-danger-600/15 dark:bg-danger-500/10 dark:text-danger-500 dark:ring-danger-500/25', dot: 'bg-danger-500' },
  info: { chip: 'bg-sky-50 text-sky-800 ring-sky-600/15 dark:bg-sky-500/10 dark:text-sky-300 dark:ring-sky-500/25', dot: 'bg-sky-500' },
}

/** Status chip: colour is always paired with text, and a dot for scanning. */
export function Badge({ tone = 'neutral', children, dot = true, className }: { tone?: BadgeTone; children: ReactNode; dot?: boolean; className?: string }) {
  return (
    <span
      className={cx(
        'inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap ring-1 ring-inset',
        BADGE_TONES[tone].chip,
        className,
      )}
    >
      {dot && <span className={cx('h-1.5 w-1.5 shrink-0 rounded-full', BADGE_TONES[tone].dot)} aria-hidden="true" />}
      {children}
    </span>
  )
}

/** Two-to-four option toggle (e.g. Gross / Net). Buttons expose their state via aria-pressed. */
export function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
  label,
}: {
  options: { value: T; label: ReactNode }[]
  value: T
  onChange: (value: T) => void
  label: string
}) {
  return (
    <div role="group" aria-label={label} className="inline-flex rounded-lg bg-zinc-100 p-0.5 text-xs font-medium dark:bg-zinc-800">
      {options.map((option) => {
        const active = option.value === value
        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(option.value)}
            className={cx(
              'rounded-md px-3 py-1.5 transition-colors duration-150',
              active
                ? 'bg-white text-zinc-900 shadow-card dark:bg-zinc-950 dark:text-zinc-50'
                : 'text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100',
            )}
          >
            {option.label}
          </button>
        )
      })}
    </div>
  )
}

export function Skeleton({ className }: { className?: string }) {
  return <span aria-hidden="true" className={cx('block animate-shimmer rounded-md bg-zinc-200/80 dark:bg-zinc-800', className)} />
}

/** A key/value row for detail panels. */
export function DetailRow({ label, children, hint }: { label: ReactNode; children: ReactNode; hint?: ReactNode }) {
  return (
    <div className="grid grid-cols-1 gap-1 py-3 sm:grid-cols-[minmax(9rem,14rem)_1fr] sm:gap-4">
      <dt className="text-sm text-zinc-500 dark:text-zinc-400">
        {label}
        {hint && <span className="mt-0.5 block text-xs text-zinc-500 dark:text-zinc-500">{hint}</span>}
      </dt>
      <dd className="min-w-0 text-sm text-zinc-900 dark:text-zinc-100">{children}</dd>
    </div>
  )
}
