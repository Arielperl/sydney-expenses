import { Bot, LayoutDashboard, Menu, PlusCircle, Receipt, Upload, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { NavLink, Outlet } from 'react-router-dom'

import { LanguageSwitcher } from './LanguageSwitcher'
import { ThemeSwitcher } from './ThemeSwitcher'

const NAV_ITEMS = [
  { to: '/', key: 'dashboard', end: true, icon: LayoutDashboard },
  { to: '/expenses', key: 'expenses', end: false, icon: Receipt },
  { to: '/add-expense', key: 'addExpense', end: false, icon: PlusCircle },
  { to: '/upload-receipt', key: 'uploadReceipt', end: false, icon: Upload },
  { to: '/assistant', key: 'assistant', end: false, icon: Bot },
] as const

function navLinkClasses(isActive: boolean): string {
  return [
    'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors',
    isActive
      ? 'bg-brand-600 text-white'
      : 'text-stone-600 hover:bg-stone-100 hover:text-stone-900 dark:text-stone-400 dark:hover:bg-stone-800 dark:hover:text-stone-100',
  ].join(' ')
}

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const { t } = useTranslation()
  return (
    <nav aria-label={t('nav.mainNavigation')} className="flex flex-1 flex-col gap-1">
      {NAV_ITEMS.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          onClick={onNavigate}
          className={({ isActive }) => navLinkClasses(isActive)}
        >
          <item.icon className="h-5 w-5" aria-hidden="true" />
          {t(`nav.${item.key}`)}
        </NavLink>
      ))}
    </nav>
  )
}

function BrandMark() {
  const { t } = useTranslation()
  return (
    <div className="flex items-center gap-2 px-2">
      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-sm font-bold text-white">
        S
      </span>
      <span className="text-lg font-semibold text-stone-900 dark:text-stone-100">{t('common.appShortName')}</span>
    </div>
  )
}

export function Layout() {
  const { t } = useTranslation()
  const [isDrawerOpen, setIsDrawerOpen] = useState(false)

  useEffect(() => {
    if (!isDrawerOpen) return
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') setIsDrawerOpen(false)
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [isDrawerOpen])

  return (
    <div className="min-h-full lg:flex">
      <aside className="hidden w-60 flex-col border-e border-stone-200 bg-white px-4 py-6 lg:flex dark:border-stone-800 dark:bg-stone-900">
        <BrandMark />
        <div className="mt-8 flex flex-1 flex-col">
          <NavLinks />
        </div>
        <div className="flex items-center gap-2">
          <LanguageSwitcher />
          <ThemeSwitcher />
        </div>
      </aside>

      <div className="flex-1">
        <header className="flex items-center justify-between border-b border-stone-200 bg-white px-4 py-3 lg:hidden dark:border-stone-800 dark:bg-stone-900">
          <BrandMark />
          <button
            type="button"
            onClick={() => setIsDrawerOpen(true)}
            aria-label={t('nav.openMenu')}
            className="flex h-9 w-9 items-center justify-center rounded-md border border-stone-300 text-stone-600 hover:bg-stone-100 dark:border-stone-700 dark:text-stone-300 dark:hover:bg-stone-800"
          >
            <Menu className="h-5 w-5" aria-hidden="true" />
          </button>
        </header>

        {isDrawerOpen && (
          <div className="fixed inset-0 z-50 lg:hidden">
            <button
              aria-label={t('common.closeDialog')}
              className="absolute inset-0 bg-stone-900/50"
              onClick={() => setIsDrawerOpen(false)}
            />
            <div className="absolute inset-y-0 start-0 flex w-64 flex-col bg-white p-4 shadow-xl dark:bg-stone-900">
              <div className="mb-6 flex items-center justify-between">
                <BrandMark />
                <button
                  type="button"
                  onClick={() => setIsDrawerOpen(false)}
                  aria-label={t('common.close')}
                  className="rounded-md p-1 text-stone-400 hover:bg-stone-100 hover:text-stone-600 dark:hover:bg-stone-800 dark:hover:text-stone-300"
                >
                  <X className="h-5 w-5" aria-hidden="true" />
                </button>
              </div>
              <NavLinks onNavigate={() => setIsDrawerOpen(false)} />
              <div className="flex items-center gap-2">
                <LanguageSwitcher />
                <ThemeSwitcher />
              </div>
            </div>
          </div>
        )}

        <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6 sm:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
