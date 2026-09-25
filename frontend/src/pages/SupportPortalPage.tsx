import { Building2, Inbox, LogOut, UsersRound } from 'lucide-react'
import type { KeyboardEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router-dom'

import logoUrl from '../assets/investment-logo.svg'
import { LanguageSwitcher } from '../components/LanguageSwitcher'
import { ThemeSwitcher } from '../components/ThemeSwitcher'
import { buttonClasses, cx } from '../components/ui-classes'
import { useAuth } from '../contexts/AuthContext'
import { BusinessesPanel } from './support-portal/BusinessesPanel'
import { StaffAccountsPanel } from './support-portal/StaffAccountsPanel'
import { SupportInbox } from './support-portal/SupportInbox'

type Section = 'inbox' | 'businesses' | 'accounts'
const SECTION_ICONS = { inbox: Inbox, businesses: Building2, accounts: UsersRound } as const

export function SupportBrand() {
  const { t } = useTranslation()
  return (
    <div className="flex min-w-0 items-center gap-2.5">
      <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-brand-50 ring-1 ring-brand-100 dark:bg-brand-500/10 dark:ring-brand-500/20">
        <img src={logoUrl} alt={t('common.logoAlt')} className="h-6 w-6 object-contain" />
      </span>
      <span className="min-w-0 leading-tight">
        <span className="block truncate text-[0.9375rem] font-semibold text-zinc-900 dark:text-zinc-50">{t('supportPortal.title')}</span>
        <span className="block text-[10px] font-medium tracking-[0.14em] text-zinc-500 uppercase dark:text-zinc-400">{t('supportPortal.brand')}</span>
      </span>
    </div>
  )
}

export function SupportPortalPage() {
  const { t } = useTranslation()
  const { user, logout } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const isSuperadmin = user?.system_role === 'superadmin'
  const sections: Section[] = isSuperadmin ? ['inbox', 'businesses', 'accounts'] : ['inbox', 'businesses']
  const requested = searchParams.get('section') as Section | null
  const section: Section = requested && sections.includes(requested) ? requested : 'inbox'

  function select(next: Section) {
    setSearchParams(next === 'inbox' ? {} : { section: next }, { replace: true })
  }

  function handleTabKey(event: KeyboardEvent<HTMLButtonElement>, current: Section) {
    const rtl = document.documentElement.dir === 'rtl'
    const index = sections.indexOf(current)
    let next: Section | null = null
    if (event.key === (rtl ? 'ArrowLeft' : 'ArrowRight')) next = sections[(index + 1) % sections.length]
    if (event.key === (rtl ? 'ArrowRight' : 'ArrowLeft')) next = sections[(index - 1 + sections.length) % sections.length]
    if (event.key === 'Home') next = sections[0]
    if (event.key === 'End') next = sections[sections.length - 1]
    if (next) {
      event.preventDefault()
      select(next)
      document.getElementById(`support-tab-${next}`)?.focus()
    }
  }

  return (
    <div className="min-h-screen bg-zinc-50 text-zinc-900 dark:bg-zinc-950 dark:text-zinc-50">
      <header className="sticky top-0 z-30 border-b border-zinc-200 bg-white/90 backdrop-blur dark:border-zinc-800 dark:bg-zinc-900/90">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <SupportBrand />
          <div className="flex min-w-0 items-center gap-1 sm:gap-2">
            <p className="hidden truncate text-xs text-zinc-500 md:block dark:text-zinc-400">
              {t('supportPortal.signedInAs')}<bdi dir="ltr">{user?.email}</bdi>
            </p>
            <LanguageSwitcher placement="bottom" />
            <ThemeSwitcher />
            <button type="button" className={buttonClasses('ghost', 'md', 'px-2.5 sm:px-3')} onClick={() => void logout()}>
              <LogOut className="h-4 w-4 rtl:-scale-x-100" aria-hidden="true" />
              <span className="hidden sm:inline">{t('supportPortal.logout')}</span>
              <span className="sr-only sm:hidden">{t('supportPortal.logout')}</span>
            </button>
          </div>
        </div>
        <div className="mx-auto max-w-6xl px-4 sm:px-6">
          <div role="tablist" aria-label={t('supportPortal.sectionsLabel')} className="-mb-px flex gap-5 overflow-x-auto">
            {sections.map((item) => {
              const Icon = SECTION_ICONS[item]
              const active = section === item
              return (
                <button
                  key={item}
                  id={`support-tab-${item}`}
                  type="button"
                  role="tab"
                  aria-selected={active}
                  aria-controls={`support-panel-${item}`}
                  tabIndex={active ? 0 : -1}
                  onClick={() => select(item)}
                  onKeyDown={(event) => handleTabKey(event, item)}
                  className={cx(
                    'inline-flex shrink-0 items-center gap-2 border-b-2 px-0.5 pt-1 pb-3 text-sm font-medium whitespace-nowrap transition-colors',
                    active
                      ? 'border-brand-600 text-zinc-900 dark:border-brand-400 dark:text-zinc-50'
                      : 'border-transparent text-zinc-500 hover:border-zinc-300 hover:text-zinc-800 dark:text-zinc-400 dark:hover:border-zinc-600 dark:hover:text-zinc-100',
                  )}
                >
                  <Icon className="h-4 w-4" aria-hidden="true" />
                  <span className="sm:hidden">{t(`supportPortal.sectionsShort.${item}`)}</span>
                  <span className="hidden sm:inline">{t(`supportPortal.sections.${item}`)}</span>
                </button>
              )
            })}
          </div>
        </div>
      </header>

      <main id="support-main" className="mx-auto max-w-6xl px-4 py-6 sm:px-6 sm:py-8">
        <h1 className="sr-only">{t('supportPortal.title')}</h1>
        <div id={`support-panel-${section}`} role="tabpanel" aria-labelledby={`support-tab-${section}`} key={section} className="animate-page-enter">
          {section === 'inbox' && <SupportInbox />}
          {section === 'businesses' && <BusinessesPanel />}
          {section === 'accounts' && user && <StaffAccountsPanel currentUserId={user.id} />}
        </div>
      </main>
    </div>
  )
}
