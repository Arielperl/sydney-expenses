import { useTranslation } from 'react-i18next'
import { NavLink, Outlet } from 'react-router-dom'

import { LanguageSwitcher } from './LanguageSwitcher'

const NAV_ITEMS = [
  { to: '/', key: 'dashboard', end: true },
  { to: '/expenses', key: 'expenses', end: false },
  { to: '/add-expense', key: 'addExpense', end: false },
  { to: '/upload-receipt', key: 'uploadReceipt', end: false },
] as const

function navLinkClasses(isActive: boolean): string {
  return [
    'rounded-md px-3 py-2 text-sm font-medium transition-colors',
    isActive ? 'bg-brand-600 text-white' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
  ].join(' ')
}

export function Layout() {
  const { t } = useTranslation()

  return (
    <div className="min-h-full">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6">
          <div className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-sm font-bold text-white">
              R
            </span>
            <span className="text-lg font-semibold text-slate-900">Receiptly</span>
          </div>
          <div className="flex flex-1 flex-wrap items-center justify-end gap-3">
            <nav aria-label={t('nav.mainNavigation')} className="flex flex-wrap items-center gap-1">
              {NAV_ITEMS.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) => navLinkClasses(isActive)}
                >
                  {t(`nav.${item.key}`)}
                </NavLink>
              ))}
            </nav>
            <LanguageSwitcher />
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6 sm:py-8">
        <Outlet />
      </main>
    </div>
  )
}
