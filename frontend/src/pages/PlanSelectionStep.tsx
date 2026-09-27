import { useMutation, useQueryClient } from '@tanstack/react-query'
import { CalendarCheck } from 'lucide-react'
import { useState } from 'react'

import { IntervalToggle, PlanCards } from '../components/billing/PlanCards'
import { useAuth } from '../contexts/AuthContext'
import { catalogSavingsMonths, formatBillingDate, planByCode } from '../lib/billing'
import { BILLING_QUERY_KEY, startTrial, type BillingInterval, type BillingOverview } from '../services/billingService'
import { PublicBrand } from './HomePage'
import './PublicPages.css'

/**
 * Onboarding, step 2 of 2: the owner picks the plan their free trial runs on.
 * Nothing is preselected and nothing is charged; the server sets the dates.
 */
export function PlanSelectionStep({ overview }: { overview: BillingOverview }) {
  const { logout } = useAuth()
  const queryClient = useQueryClient()
  const [interval, setInterval] = useState<BillingInterval>('month')
  const [planCode, setPlanCode] = useState<string | null>(null)
  const [logoutError, setLogoutError] = useState(false)
  const selected = planByCode(overview.plans, planCode)
  // A preview only; the server's own clock sets the real end date shown afterwards.
  const [previewEnd] = useState(() => new Date(Date.now() + overview.trial_days * 86_400_000).toISOString())
  const start = useMutation({
    mutationFn: () => startTrial(planCode as string, interval),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: BILLING_QUERY_KEY }),
  })

  return (
    <div className="plan-step" dir="rtl">
      <header className="plan-step-header">
        <PublicBrand />
        <span className="plan-step-progress" aria-label="שלב 2 מתוך 2">
          <span aria-hidden="true" className="done" /><span aria-hidden="true" className="done" />
          שלב 2 מתוך 2
        </span>
      </header>

      <main className="plan-step-main">
        <div className="plan-step-heading">
          <div>
            <h1>30 יום להכיר את Sydney, ללא התחייבות</h1>
            <p>בחרו מסלול והתחילו לעבוד מיד. לא נבקש כרטיס אשראי במהלך תקופת הניסיון, ואפשר להחליף מסלול בכל שלב שלה.</p>
          </div>
          <IntervalToggle surface="public" value={interval} onChange={setInterval} savingsMonths={catalogSavingsMonths(overview.plans)} />
        </div>

        <form
          onSubmit={(event) => {
            event.preventDefault()
            if (planCode) start.mutate()
          }}
        >
          <PlanCards
            plans={overview.plans}
            interval={interval}
            surface="public"
            selection={{ name: 'onboarding-plan', value: planCode, onChange: setPlanCode, label: 'בחירת מסלול לתקופת הניסיון' }}
          />

          <div className="plan-step-summary" aria-live="polite">
            <span className="feature-icon" aria-hidden="true"><CalendarCheck size={18} /></span>
            <div className="plan-step-summary-text">
              {selected ? (
                <>
                  <strong>מסלול <bdi dir="ltr">{selected.name}</bdi> · תקופת ניסיון עד {formatBillingDate(previewEnd, overview.business_timezone, 'he')}</strong>
                  <span>לא יתבצע חיוב בתקופת הניסיון. שבוע לפני הסיום נזכיר לכם להוסיף אמצעי תשלום.</span>
                </>
              ) : (
                <>
                  <strong>בחרו מסלול כדי להתחיל</strong>
                  <span>המחירים לפני מע״מ. {overview.trial_days} ימי הניסיון חינם ואינם דורשים אמצעי תשלום.</span>
                </>
              )}
            </div>
            <button type="submit" className="public-button" disabled={!planCode || start.isPending}>
              {start.isPending ? 'מתחילים…' : 'התחלת תקופת הניסיון'}
            </button>
          </div>
          {start.isError && <p className="auth-message error" role="alert">{start.error.message || 'לא הצלחנו להתחיל את תקופת הניסיון. נסו שוב.'}</p>}
        </form>

        <button
          type="button"
          className="auth-forgot"
          onClick={() => { setLogoutError(false); void logout().catch(() => setLogoutError(true)) }}
        >
          התנתקות
        </button>
        {logoutError && <p className="auth-message error" role="alert">ההתנתקות נכשלה. נסו שוב.</p>}
      </main>
    </div>
  )
}
