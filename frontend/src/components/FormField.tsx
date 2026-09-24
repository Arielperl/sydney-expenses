import type { ReactNode } from 'react'

export function FormField({
  label,
  htmlFor,
  error,
  required,
  children,
  hint,
}: {
  label: string
  htmlFor: string
  error?: string
  required?: boolean
  hint?: string
  children: ReactNode
}) {
  return (
    <div>
      <label htmlFor={htmlFor} className="block text-sm font-medium text-zinc-800 dark:text-zinc-200">
        {label}
        {required && <span className="text-danger-600 dark:text-danger-500" aria-hidden="true"> *</span>}
      </label>
      <div className="mt-1.5">{children}</div>
      {hint && !error && <p className="mt-1.5 text-xs leading-relaxed text-zinc-500 dark:text-zinc-400">{hint}</p>}
      {error && (
        <p role="alert" className="mt-1.5 text-xs font-medium text-danger-700 dark:text-danger-500">
          {error}
        </p>
      )}
    </div>
  )
}

export const inputClasses =
  'block w-full min-h-10 rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 shadow-card transition-[border-color,box-shadow] duration-150 placeholder:text-zinc-400 hover:border-zinc-400 focus:border-brand-500 focus:ring-3 focus:ring-brand-500/15 focus:outline-none aria-[invalid=true]:border-danger-500 disabled:cursor-not-allowed disabled:bg-zinc-50 disabled:text-zinc-500 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:placeholder:text-zinc-500 dark:hover:border-zinc-600 dark:focus:border-brand-400 dark:disabled:bg-zinc-800'
