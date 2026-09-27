import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, CalendarCheck, ChevronDown, CreditCard, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { IntervalToggle, PlanCards } from '../components/billing/PlanCards'
import { catalogSavingsMonths } from '../lib/billing'
import { getPlanCatalog, PLAN_CATALOG_QUERY_KEY, type BillingInterval } from '../services/billingService'
import { PublicFooter, PublicHeader } from './HomePage'
import './PublicPages.css'

const ASSURANCES = [
  { icon: CalendarCheck, title: '30 יום ללא עלות', text: 'תקופת הניסיון מתחילה כשבוחרים מסלול, ותאריך הסיום מוצג תמיד בעמוד המנוי.' },
  { icon: CreditCard, title: 'בלי כרטיס אשראי', text: 'לא נבקש אמצעי תשלום במהלך הניסיון ולא נחייב דבר עד שתבחרו להמשיך.' },
  { icon: ShieldCheck, title: 'הנתונים נשארים שלכם', text: 'גם אם תקופת הניסיון מסתיימת, המכירות והנתונים של העסק נשמרים ולא נמחקים.' },
] as const

const PRICING_FAQ = [
  ['מה קורה בסוף תקופת הניסיון?', 'כדי להמשיך להשתמש במערכת בוחרים מסלול ומשלימים את התשלום. אם לא ממשיכים, הגישה לכלים נעצרת, אבל הנתונים נשמרים ואפשר לחזור אליהם בכל עת בבחירת מסלול.'],
  ['האם המחירים כוללים מע״מ?', 'לא. כל המחירים בעמוד מוצגים לפני מע״מ, והמע״מ יתווסף בחשבונית לפי השיעור שבתוקף.'],
  ['אפשר להחליף מסלול?', 'כן. במהלך תקופת הניסיון ההחלפה מיידית. במנוי בתשלום, מעבר למסלול גבוה יותר חל מיד, ומעבר למסלול נמוך יותר חל בתחילת התקופה הבאה.'],
  ['איך מבטלים?', 'בעמוד ״מנוי וחיוב״ מבטלים את החידוש בלחיצה. הביטול נכנס לתוקף בסוף התקופה ששולמה, ועד אז הכול ממשיך לעבוד כרגיל.'],
] as const

function PlanCardsSkeleton() {
  return (
    <div className="grid gap-5 md:grid-cols-3 lg:gap-6" role="status" aria-label="טוענים את המסלולים">
      {[0, 1, 2].map((index) => (
        <div key={index} className="h-[31rem] animate-shimmer rounded-2xl border border-zinc-200 bg-zinc-50" aria-hidden="true" />
      ))}
    </div>
  )
}

export function PricingPage() {
  const [interval, setInterval] = useState<BillingInterval>('month')
  const catalog = useQuery({ queryKey: PLAN_CATALOG_QUERY_KEY, queryFn: getPlanCatalog, staleTime: 5 * 60_000 })
  const plans = catalog.data?.plans ?? []

  return (
    <div className="public-site" dir="rtl">
      <PublicHeader current="pricing" />
      <main>
        <section className="pricing-section" aria-labelledby="pricing-heading">
          <div className="section-heading split">
            <div>
              <span className="eyebrow">מחירים</span>
              <h1 id="pricing-heading">30 יום להכיר את Sydney,<br />ללא התחייבות</h1>
            </div>
            <p>בחרו מסלול והתחילו לעבוד מיד. לא נבקש כרטיס אשראי במהלך תקופת הניסיון.</p>
          </div>

          <div className="pricing-controls">
            <IntervalToggle surface="public" value={interval} onChange={setInterval} savingsMonths={catalogSavingsMonths(plans)} />
            <span className="pricing-vat-note">כל המחירים לפני מע״מ</span>
          </div>

          {catalog.isPending && <PlanCardsSkeleton />}
          {catalog.isError && (
            <div className="pricing-error" role="alert">
              <p>לא הצלחנו לטעון את המסלולים כרגע.</p>
              <button type="button" className="public-button small" onClick={() => void catalog.refetch()}>ניסיון נוסף</button>
            </div>
          )}
          {catalog.data && (
            <PlanCards
              plans={plans}
              interval={interval}
              surface="public"
              showMembers={catalog.data.member_limits_available}
              headingLevel="h2"
              renderAction={(plan) => (
                <Link
                  to="/signup"
                  className={plan.recommended ? 'public-button pricing-cta' : 'public-button outline pricing-cta'}
                  aria-label={`מתחילים ניסיון חינם במסלול ${plan.name}`}
                >
                  מתחילים ניסיון חינם
                </Link>
              )}
            />
          )}

          <ul className="pricing-assurances">
            {ASSURANCES.map(({ icon: Icon, title, text }) => (
              <li key={title}>
                <span className="feature-icon" aria-hidden="true"><Icon size={18} /></span>
                <div><h3>{title}</h3><p>{text}</p></div>
              </li>
            ))}
          </ul>
        </section>

        <section className="public-section faq-section" id="pricing-faq">
          <div>
            <span className="eyebrow">על המנוי</span>
            <h2>מה חשוב לדעת<br />לפני שבוחרים.</h2>
          </div>
          <div className="faq-list">
            {PRICING_FAQ.map(([question, answer]) => (
              <details key={question}><summary>{question}<ChevronDown size={18} aria-hidden="true" /></summary><p>{answer}</p></details>
            ))}
          </div>
        </section>

        <section className="public-cta">
          <span className="eyebrow">בלי כרטיס אשראי</span>
          <h2>מתחילים היום.<br />מחליטים בעוד 30 יום.</h2>
          <Link to="/signup" className="public-button on-dark">פתיחת חשבון <ArrowLeft size={18} aria-hidden="true" /></Link>
        </section>
      </main>
      <PublicFooter />
    </div>
  )
}
