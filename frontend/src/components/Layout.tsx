import { useQuery } from '@tanstack/react-query'
import { Bot, ChevronUp, Home, LayoutDashboard, ListTodo, LogOut, Menu, PlugZap, ShieldCheck, ShoppingCart, UserRound, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { NavLink, Outlet } from 'react-router-dom'

import logoUrl from '../assets/investment-logo.svg'
import { useAuth } from '../contexts/AuthContext'
import { getExceptionCenter } from '../services/exceptionService'
import { BusinessBadge } from './BusinessBadge'
import { LanguageSwitcher } from './LanguageSwitcher'
import { ThemeSwitcher } from './ThemeSwitcher'

const NAV_ITEMS = [
  { to: '/app', key: 'dashboard', end: true, icon: LayoutDashboard },
  { to: '/sales', key: 'sales', end: false, icon: ShoppingCart },
  { to: '/exceptions', key: 'exceptions', end: false, icon: ListTodo },
  { to: '/imports', key: 'imports', end: false, icon: PlugZap },
  { to: '/assistant', key: 'assistant', end: false, icon: Bot },
] as const

function navLinkClasses(isActive: boolean): string {
  return [
    'group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors',
    isActive
      ? 'active bg-brand-600 text-white'
      : 'text-stone-600 hover:bg-stone-100 hover:text-stone-900 dark:text-stone-400 dark:hover:bg-stone-800 dark:hover:text-stone-100',
  ].join(' ')
}

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const { t } = useTranslation()
  const { user } = useAuth()
  const { data: attentionCount = 0 } = useQuery({
    queryKey: ['exception-center'],
    queryFn: () => getExceptionCenter(),
    select: (data) => data.attention_count,
    refetchInterval: 60_000,
  })

  return (
    <nav aria-label={t('nav.mainNavigation')} className="flex flex-1 flex-col gap-1">
      {NAV_ITEMS.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          onClick={onNavigate}
          aria-label={item.key === 'exceptions' && attentionCount > 0
            ? t('nav.attentionCount', { count: attentionCount })
            : undefined}
          className={({ isActive }) => navLinkClasses(isActive)}
        >
          <item.icon className="h-5 w-5" aria-hidden="true" />
          <span className="min-w-0 flex-1">{t(`nav.${item.key}`)}</span>
          {item.key === 'exceptions' && attentionCount > 0 && (
            <span
              className="grid h-5 min-w-5 place-items-center rounded-full bg-amber-100 px-1.5 text-xs font-bold leading-none text-amber-800 group-[.active]:bg-white/20 group-[.active]:text-white dark:bg-amber-500/20 dark:text-amber-300"
              aria-hidden="true"
            >
              {attentionCount > 99 ? '99+' : attentionCount}
            </span>
          )}
        </NavLink>
      ))}
      {user?.system_role === 'admin' && <NavLink to="/admin" onClick={onNavigate} className={({ isActive }) => navLinkClasses(isActive)}><ShieldCheck className="h-5 w-5"/><span className="min-w-0 flex-1">{t('nav.admin')}</span></NavLink>}
    </nav>
  )
}

function BrandMark() {
  const { t } = useTranslation()
  return (
    <div className="flex min-w-0 items-center gap-2 px-2">
      <img src={logoUrl} alt={t('common.logoAlt')} className="h-8 w-8 shrink-0 object-contain" />
      <span className="truncate text-base font-semibold text-stone-900 dark:text-stone-100">
        {t('common.appShortName')}
      </span>
    </div>
  )
}

function AccountMenu({ onNavigate }: { onNavigate?: () => void }) {
  const { t } = useTranslation()
  const { logout, user } = useAuth()
  const [isOpen, setIsOpen] = useState(false)
  const [logoutError, setLogoutError] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)
  const displayName = user?.name?.trim() || t('account.myAccount')
  const initial = (user?.name?.trim() || user?.email || '?').charAt(0).toLocaleUpperCase()

  useEffect(() => {
    if (!isOpen) return
    function closeOnOutsideClick(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) setIsOpen(false)
    }
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') setIsOpen(false)
    }
    document.addEventListener('mousedown', closeOnOutsideClick)
    document.addEventListener('keydown', closeOnEscape)
    return () => {
      document.removeEventListener('mousedown', closeOnOutsideClick)
      document.removeEventListener('keydown', closeOnEscape)
    }
  }, [isOpen])

  async function handleLogout() {
    setLogoutError(false)
    try {
      await logout()
      onNavigate?.()
    } catch {
      setLogoutError(true)
    }
  }

  return (
    <div ref={rootRef} className="relative mt-3 border-t border-stone-200 pt-3 dark:border-stone-800">
      {isOpen && (
        <div
          role="menu"
          className="absolute inset-x-0 bottom-full z-20 mb-2 overflow-hidden rounded-xl border border-stone-200 bg-white p-2 shadow-xl shadow-stone-900/10 dark:border-stone-700 dark:bg-stone-800"
        >
          <div className="border-b border-stone-100 px-3 py-2.5 dark:border-stone-700">
            <p className="truncate text-sm font-semibold text-stone-900 dark:text-stone-100">{displayName}</p>
            <p className="mt-0.5 truncate text-xs text-stone-500 dark:text-stone-400" dir="ltr">{user?.email}</p>
          </div>
          <NavLink
            to="/"
            role="menuitem"
            onClick={() => { setIsOpen(false); onNavigate?.() }}
            className="mt-1 flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-stone-600 hover:bg-stone-100 hover:text-stone-900 dark:text-stone-300 dark:hover:bg-stone-700 dark:hover:text-white"
          >
            <Home className="h-4 w-4" aria-hidden="true" />
            {t('account.backToWebsite')}
          </NavLink>
          <button
            type="button"
            role="menuitem"
            onClick={() => void handleLogout()}
            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-danger-600 hover:bg-danger-50 dark:text-danger-500 dark:hover:bg-danger-500/10"
          >
            <LogOut className="h-4 w-4" aria-hidden="true" />
            {t('account.logout')}
          </button>
          {logoutError && <p className="px-3 pb-2 text-xs text-danger-600" role="alert">{t('account.logoutError')}</p>}
        </div>
      )}

      <button
        type="button"
        aria-expanded={isOpen}
        aria-haspopup="menu"
        onClick={() => setIsOpen((open) => !open)}
        className="flex w-full items-center gap-3 rounded-xl border border-transparent p-2 text-start transition-colors hover:border-stone-200 hover:bg-stone-50 dark:hover:border-stone-700 dark:hover:bg-stone-800"
      >
        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-brand-100 text-sm font-bold text-brand-800 dark:bg-brand-900 dark:text-brand-200" aria-hidden="true">
          {initial || <UserRound className="h-4 w-4" />}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-semibold text-stone-800 dark:text-stone-100">{displayName}</span>
          <span className="block truncate text-xs text-stone-500 dark:text-stone-400" dir="ltr">{user?.email}</span>
        </span>
        <ChevronUp className={`h-4 w-4 shrink-0 text-stone-400 transition-transform ${isOpen ? 'rotate-180' : ''}`} aria-hidden="true" />
        <span className="sr-only">{t('account.openMenu')}</span>
      </button>
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
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col overflow-hidden border-e border-stone-200 bg-white px-4 py-6 lg:flex dark:border-stone-800 dark:bg-stone-900">
        <BrandMark />
        <div className="mt-3 px-2">
          <BusinessBadge />
        </div>
        <div className="mt-8 flex min-h-0 flex-1 flex-col overflow-y-auto">
          <NavLinks />
        </div>
        <div className="flex shrink-0 items-center gap-2 pt-3">
          <LanguageSwitcher />
          <ThemeSwitcher />
        </div>
        <AccountMenu />
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
              <div className="mb-4">
                <BusinessBadge />
              </div>
              <div className="min-h-0 flex-1 overflow-y-auto">
                <NavLinks onNavigate={() => setIsDrawerOpen(false)} />
              </div>
              <div className="flex shrink-0 items-center gap-2 pt-3">
                <LanguageSwitcher />
                <ThemeSwitcher />
              </div>
              <AccountMenu onNavigate={() => setIsDrawerOpen(false)} />
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
