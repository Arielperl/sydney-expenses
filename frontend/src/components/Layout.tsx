import { useQuery } from '@tanstack/react-query'
import { Bot, ChevronsUpDown, Home, LayoutDashboard, ListTodo, LogOut, Menu, PlugZap, ShieldCheck, ShoppingCart, UserRound, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { NavLink, Outlet, useLocation } from 'react-router-dom'

import logoUrl from '../assets/investment-logo.svg'
import { useAuth } from '../contexts/AuthContext'
import { getExceptionCenter } from '../services/exceptionService'
import { BusinessBadge } from './BusinessBadge'
import { LanguageSwitcher } from './LanguageSwitcher'
import { ThemeSwitcher } from './ThemeSwitcher'
import { cx } from './ui-classes'

const NAV_ITEMS = [
  { to: '/app', key: 'dashboard', end: true, icon: LayoutDashboard },
  { to: '/sales', key: 'sales', end: false, icon: ShoppingCart },
  { to: '/exceptions', key: 'exceptions', end: false, icon: ListTodo },
  { to: '/imports', key: 'imports', end: false, icon: PlugZap },
  { to: '/assistant', key: 'assistant', end: false, icon: Bot },
] as const

function navLinkClasses(isActive: boolean): string {
  return cx(
    'group relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors duration-150',
    // The start-edge bar marks the current page without shouting.
    'before:absolute before:inset-y-2 before:start-0 before:w-[3px] before:rounded-full before:bg-brand-600 before:opacity-0 before:transition-opacity dark:before:bg-brand-400',
    isActive
      ? 'active bg-brand-50 font-semibold text-brand-800 before:opacity-100 dark:bg-brand-500/10 dark:text-brand-200'
      : 'font-medium text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800/70 dark:hover:text-zinc-100',
  )
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
    <nav aria-label={t('nav.mainNavigation')} className="flex flex-1 flex-col gap-0.5">
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
          <item.icon className="h-[18px] w-[18px] shrink-0 opacity-80 group-[.active]:opacity-100" aria-hidden="true" />
          <span className="min-w-0 flex-1 truncate">{t(`nav.${item.key}`)}</span>
          {item.key === 'exceptions' && attentionCount > 0 && (
            <span
              className="figure grid h-5 min-w-5 place-items-center rounded-full bg-amber-100 px-1.5 text-[11px] font-semibold leading-none text-amber-900 dark:bg-amber-500/20 dark:text-amber-200"
              aria-hidden="true"
            >
              {attentionCount > 99 ? '99+' : attentionCount}
            </span>
          )}
        </NavLink>
      ))}
      {user?.system_role === 'admin' && (
        <>
          <div className="mx-3 my-3 border-t border-zinc-200 dark:border-zinc-800" aria-hidden="true" />
          <NavLink to="/admin" onClick={onNavigate} className={({ isActive }) => navLinkClasses(isActive)}>
            <ShieldCheck className="h-[18px] w-[18px] shrink-0 opacity-80" aria-hidden="true" />
            <span className="min-w-0 flex-1 truncate">{t('nav.admin')}</span>
          </NavLink>
        </>
      )}
    </nav>
  )
}

function BrandMark() {
  const { t } = useTranslation()
  return (
    <div className="flex min-w-0 items-center gap-2.5">
      <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-brand-50 ring-1 ring-brand-100 dark:bg-brand-500/10 dark:ring-brand-500/20">
        <img src={logoUrl} alt={t('common.logoAlt')} className="h-6 w-6 object-contain" />
      </span>
      <span className="min-w-0 leading-tight">
        <span className="block truncate text-[0.9375rem] font-semibold text-zinc-900 dark:text-zinc-50">{t('common.appShortName')}</span>
        <span className="block text-[10px] font-medium tracking-[0.14em] text-zinc-500 uppercase dark:text-zinc-400">Sydney</span>
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
    <div ref={rootRef} className="relative">
      {isOpen && (
        <div
          role="menu"
          className="absolute inset-x-0 bottom-full z-20 mb-2 animate-pop-in overflow-hidden rounded-xl border border-zinc-200 bg-white p-1.5 shadow-raised dark:border-zinc-700 dark:bg-zinc-900"
        >
          <div className="border-b border-zinc-100 px-3 py-2.5 dark:border-zinc-800">
            <p className="truncate text-sm font-semibold text-zinc-900 dark:text-zinc-100">{displayName}</p>
            <p className="mt-0.5 truncate text-xs text-zinc-500 dark:text-zinc-400" dir="ltr">{user?.email}</p>
          </div>
          <NavLink
            to="/"
            role="menuitem"
            onClick={() => { setIsOpen(false); onNavigate?.() }}
            className="mt-1 flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-zinc-700 hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800 dark:hover:text-white"
          >
            <Home className="h-4 w-4" aria-hidden="true" />
            {t('account.backToWebsite')}
          </NavLink>
          <button
            type="button"
            role="menuitem"
            onClick={() => void handleLogout()}
            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-danger-700 hover:bg-danger-50 dark:text-danger-500 dark:hover:bg-danger-500/10"
          >
            <LogOut className="h-4 w-4" aria-hidden="true" />
            {t('account.logout')}
          </button>
          {logoutError && <p className="px-3 pb-2 text-xs text-danger-700 dark:text-danger-500" role="alert">{t('account.logoutError')}</p>}
        </div>
      )}

      <button
        type="button"
        aria-expanded={isOpen}
        aria-haspopup="menu"
        onClick={() => setIsOpen((open) => !open)}
        className="flex w-full items-center gap-3 rounded-lg p-2 text-start transition-colors hover:bg-zinc-100 dark:hover:bg-zinc-800/70"
      >
        <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-brand-100 text-sm font-semibold text-brand-800 dark:bg-brand-500/15 dark:text-brand-200" aria-hidden="true">
          {initial || <UserRound className="h-4 w-4" />}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium text-zinc-800 dark:text-zinc-100">{displayName}</span>
          <span className="block truncate text-xs text-zinc-500 dark:text-zinc-400" dir="ltr">{user?.email}</span>
        </span>
        <ChevronsUpDown className="h-4 w-4 shrink-0 text-zinc-400" aria-hidden="true" />
        <span className="sr-only">{t('account.openMenu')}</span>
      </button>
    </div>
  )
}

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <>
      <div className="px-2">
        <BusinessBadge />
      </div>
      <div className="mt-5 flex min-h-0 flex-1 flex-col overflow-y-auto px-0.5">
        <NavLinks onNavigate={onNavigate} />
      </div>
      <div className="mt-3 space-y-2 border-t border-zinc-200 pt-3 dark:border-zinc-800">
        <div className="flex items-center gap-1.5 px-1">
          <LanguageSwitcher />
          <ThemeSwitcher />
        </div>
        <AccountMenu onNavigate={onNavigate} />
      </div>
    </>
  )
}

export function Layout() {
  const { t } = useTranslation()
  const location = useLocation()
  const [isDrawerOpen, setIsDrawerOpen] = useState(false)
  const closeButtonRef = useRef<HTMLButtonElement>(null)
  const menuButtonRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!isDrawerOpen) return
    const menuButton = menuButtonRef.current
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    closeButtonRef.current?.focus()
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') setIsDrawerOpen(false)
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.body.style.overflow = previousOverflow
      document.removeEventListener('keydown', handleKeyDown)
      menuButton?.focus()
    }
  }, [isDrawerOpen])

  return (
    <div className="min-h-full lg:flex">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:start-3 focus:top-3 focus:z-[60] focus:rounded-lg focus:bg-white focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:shadow-raised dark:focus:bg-zinc-900"
      >
        {t('nav.skipToContent')}
      </a>

      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-e border-zinc-200/80 bg-white/70 px-3 py-5 backdrop-blur lg:flex dark:border-zinc-800 dark:bg-zinc-900/60">
        <div className="mb-5 px-2">
          <BrandMark />
        </div>
        <SidebarContent />
      </aside>

      <div className="min-w-0 flex-1">
        <header className="sticky top-0 z-30 flex items-center justify-between border-b border-zinc-200/80 bg-white/85 px-4 py-2.5 backdrop-blur-md lg:hidden dark:border-zinc-800 dark:bg-zinc-900/85">
          <BrandMark />
          <button
            ref={menuButtonRef}
            type="button"
            onClick={() => setIsDrawerOpen(true)}
            aria-label={t('nav.openMenu')}
            aria-expanded={isDrawerOpen}
            className="grid h-10 w-10 place-items-center rounded-lg text-zinc-700 transition-colors hover:bg-zinc-100 dark:text-zinc-200 dark:hover:bg-zinc-800"
          >
            <Menu className="h-5 w-5" aria-hidden="true" />
          </button>
        </header>

        {isDrawerOpen && (
          <div className="fixed inset-0 z-50 lg:hidden">
            <button
              aria-label={t('common.closeDialog')}
              className="absolute inset-0 animate-fade-in bg-zinc-950/40 backdrop-blur-[2px]"
              onClick={() => setIsDrawerOpen(false)}
            />
            <div
              role="dialog"
              aria-modal="true"
              aria-label={t('nav.mainNavigation')}
              className="absolute inset-y-0 start-0 flex w-[min(20rem,86vw)] animate-drawer-in flex-col bg-white px-3 py-4 shadow-raised dark:bg-zinc-900"
            >
              <div className="mb-5 flex items-center justify-between px-2">
                <BrandMark />
                <button
                  ref={closeButtonRef}
                  type="button"
                  onClick={() => setIsDrawerOpen(false)}
                  aria-label={t('common.close')}
                  className="grid h-9 w-9 place-items-center rounded-lg text-zinc-500 hover:bg-zinc-100 hover:text-zinc-800 dark:hover:bg-zinc-800 dark:hover:text-zinc-200"
                >
                  <X className="h-5 w-5" aria-hidden="true" />
                </button>
              </div>
              <SidebarContent onNavigate={() => setIsDrawerOpen(false)} />
            </div>
          </div>
        )}

        <main id="main-content" tabIndex={-1} className="mx-auto w-full max-w-[1200px] px-4 py-6 outline-none sm:px-6 sm:py-8 lg:px-10 lg:py-10">
          {/* Keyed by route so each screen arrives with the same short, calm entrance. */}
          <div key={location.pathname} className="animate-page-enter">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}
