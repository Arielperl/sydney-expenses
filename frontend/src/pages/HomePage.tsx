import { Link } from 'react-router-dom'
import { ArrowLeft, Check, ChartNoAxesCombined, Zap, ShieldCheck, MessageSquare, PlugZap, ChevronDown } from 'lucide-react'
import logo from '../assets/investment-logo.svg'
import './PublicPages.css'
import { useLandingMotion } from '../hooks/useLandingMotion'

export function PublicBrand() {
  return (
    <Link to="/" className="public-brand">
      <span className="public-brand-mark"><img src={logo} alt="" /></span>
      <span>מנהל הכנסות<small>מבית SYDNEY</small></span>
    </Link>
  )
}

/*
 * Illustrative product preview. Every figure is labelled as illustrative and
 * the breakdown reconciles exactly: 30,620.00 − 4,670.85 − 643.02 − 456.13 =
 * 24,850.00. No growth claims or invented comparisons.
 */
const PREVIEW_ROWS: [string, string][] = [
  ['הכנסה ברוטו', '₪30,620.00'],
  ['מע״מ הכלול בברוטו', '₪4,670.85'],
  ['עמלות סליקה', '₪643.02'],
  ['החזרים חלקיים', '₪456.13'],
]

export function ProductPreview() {
  return (
    <div className="product-preview" aria-label="תצוגה להמחשה של לוח ההכנסות">
      <div className="preview-top">
        <span>סיכום התקופה</span>
        <span className="preview-pill">נתונים להמחשה · ספטמבר</span>
      </div>
      <div className="preview-figure">
        <small>תקבולים נטו לאחר ניכויים</small>
        <strong><bdi>₪24,850.00</bdi></strong>
        <span>ברוטו בניכוי מע״מ, עמלות והחזרים. אינו רווח ואינו יתרת חשבון.</span>
      </div>
      <div className="preview-chart" aria-hidden="true">
        <svg viewBox="0 0 600 120" preserveAspectRatio="none">
          <defs>
            <linearGradient id="preview-fill" x1="0" x2="0" y1="0" y2="1">
              <stop stopColor="#47b395" stopOpacity=".32" />
              <stop offset="1" stopColor="#47b395" stopOpacity="0" />
            </linearGradient>
          </defs>
          <path d="M0 96 C40 92 60 70 95 76 S150 98 190 72 S245 80 285 58 S340 66 380 44 S430 54 470 34 S540 40 600 22 L600 120 L0 120Z" fill="url(#preview-fill)" />
          <path d="M0 96 C40 92 60 70 95 76 S150 98 190 72 S245 80 285 58 S340 66 380 44 S430 54 470 34 S540 40 600 22" stroke="#7ccdb5" strokeWidth="2" fill="none" vectorEffect="non-scaling-stroke" />
        </svg>
      </div>
      <dl className="preview-rows">
        {PREVIEW_ROWS.map(([label, value]) => (
          <div key={label}><dt>{label}</dt><dd><bdi>{value}</bdi></dd></div>
        ))}
      </dl>
    </div>
  )
}

const features = [
  { icon: ChartNoAxesCombined, title: 'התמונה המלאה, במבט אחד', text: 'מכירות, מע״מ, עמלות וזיכויים — עם פירוט שמבהיר איך מתקבל כל סכום.' },
  { icon: Zap, title: 'מכירה חדשה. עדכון אוטומטי.', text: 'חיבור למערכת התשלומים מאפשר לקלוט עסקאות בלי להזין כל מכירה מחדש.' },
  { icon: ShieldCheck, title: 'יודעים מה דורש טיפול', text: 'מסמכים חסרים או כאלה שלא הגיעו בזמן מופיעים ברשימת טיפול ברורה, בלי להעמיס עסקאות תקינות.' },
  { icon: MessageSquare, title: 'שואלים את הנתונים שלכם', text: 'איזה שירות מכר הכי הרבה? כמה נכנס החודש? העוזר עוזר למצוא תשובות.' },
]

const steps: [string, string, string][] = [
  ['01', 'מחברים את מקור המכירות', 'מגדירים חיבור למערכת התשלומים בעזרת ממשק החיבורים.'],
  ['02', 'העסקאות נקלטות', 'פרטי הלקוח, השירות והתשלום מתרכזים ברשימת המכירות.'],
  ['03', 'רואים את מצב העסק', 'עוקבים אחרי הכנסות ומגמות ומטפלים בחריגים בזמן.'],
]

const faq: [string, string][] = [
  ['צריך להעלות כל קבלה ידנית?', 'לאחר הגדרת חיבור מתאים, פרטי העסקאות יכולים להיקלט אוטומטית. אפשר גם להזין מכירה ידנית במערכת.'],
  ['האם המערכת מחליפה רואה חשבון?', 'המערכת מרכזת את נתוני המכירות והתקבולים. היא אינה מחליפה רואה חשבון או שירות הנהלת חשבונות.'],
  ['מה ההבדל בין תקבולים נטו לרווח?', 'התקבולים מוצגים לאחר הניכויים המפורטים במערכת. הם אינם רווח נקי, כי הוצאות העסק אינן נכללות בחישוב.'],
  ['מה קורה אחרי ההרשמה?', 'מאמתים את כתובת האימייל ומתחברים. המוצר נמצא בשלב ההרצה; הגישה לסביבת העסק נפתחת לאחר שיוך החשבון לעסק.'],
]

export function HomePage() {
  const motionRef = useLandingMotion()
  return (
    <div ref={motionRef} className="public-site" dir="rtl">
      <header className="public-header">
        <PublicBrand />
        <nav aria-label="ניווט באתר">
          <a href="#features">יכולות</a>
          <a href="#how">איך זה עובד</a>
          <a href="#connections">חיבורים</a>
          <a href="#faq">שאלות נפוצות</a>
        </nav>
        <div className="header-actions">
          <Link to="/login" className="header-login">התחברות</Link>
          <Link className="public-button small" to="/signup">פתיחת חשבון <ArrowLeft size={16} aria-hidden="true" /></Link>
        </div>
      </header>

      <main>
        <section className="public-hero">
          <div className="hero-image" aria-hidden="true" />
          <div className="hero-inner">
            <div className="hero-copy">
              <span className="eyebrow">מנהל הכנסות לעסקים</span>
              <h1>מכירות, הכנסות<br />ומה שדורש טיפול.<br /><span>במקום אחד.</span></h1>
              <p>מרכזים עסקאות ממקורות מחוברים, עוקבים אחרי הנתונים הכספיים ורואים אילו מכירות צריכות פעולה.</p>
              <div className="hero-actions">
                <Link to="/signup" className="public-button on-dark">מתחילים לנהל הכנסות <ArrowLeft size={18} aria-hidden="true" /></Link>
                <a className="public-button ghost" href="#preview">לראות איך זה עובד</a>
              </div>
              <ul className="hero-notes">
                <li><Check size={15} aria-hidden="true" /> מותאם לעברית</li>
                <li><Check size={15} aria-hidden="true" /> תמונה כספית ברורה</li>
                <li><Check size={15} aria-hidden="true" /> פחות עבודה ידנית</li>
              </ul>
            </div>
            <div className="hero-product" id="preview">
              <ProductPreview />
              <p className="preview-caption">המחשת המוצר · הנתונים אינם נתוני עסק אמיתי</p>
            </div>
          </div>
          <div className="hero-bottom">
            <span>נבנה לעסקים קטנים. חושב על הפרטים הגדולים.</span>
            <a href="#features" aria-label="לגלות את היכולות"><ChevronDown size={20} aria-hidden="true" /></a>
          </div>
        </section>

        <section className="public-section features" id="features">
          <div className="section-heading split">
            <div>
              <span className="eyebrow">כל העסק, בפרספקטיבה</span>
              <h2>המספרים במקום אחד.<br />הראש פנוי לעסק.</h2>
            </div>
            <p>פחות מעבר בין דוחות ומערכות. יותר זמן להבין מה עובד ולפעול בהתאם.</p>
          </div>
          <div className="feature-grid">
            {features.map((feature) => (
              <article key={feature.title}>
                <span className="feature-icon" aria-hidden="true"><feature.icon size={20} /></span>
                <h3>{feature.title}</h3>
                <p>{feature.text}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="how-band" id="how">
          <div className="public-section how-section">
            <div className="section-heading split">
              <div>
                <span className="eyebrow">מתחברים. מוכרים. רואים.</span>
                <h2>מהעסקה הראשונה,<br />הכול מתחבר.</h2>
              </div>
              <p>שלושה צעדים, פעם אחת. מכאן והלאה כל מכירה נקלטת ומסתדרת במקום שלה.</p>
            </div>
            <ol className="steps">
              {steps.map(([number, title, text]) => (
                <li key={number}><span><bdi>{number}</bdi></span><h3>{title}</h3><p>{text}</p></li>
              ))}
            </ol>
          </div>
        </section>

        <section className="public-section connection-section" id="connections">
          <div className="connection-art" aria-hidden="true">
            <div className="sources"><span>Grow</span><span>Cardcom</span><span><PlugZap size={14} /> CSV</span></div>
            <i /><div><img src={logo} alt="" /></div><i /><div><ChartNoAxesCombined size={32} /></div>
          </div>
          <div>
            <span className="eyebrow">המערכות שלכם, יחד</span>
            <h2>המידע מגיע.<br />אתם ממשיכים לעבוד.</h2>
            <p>מחברים את מערכת התשלומים והמכירות נכנסות אוטומטית ברגע שהן מתבצעות. אפשר גם להעלות קובץ עם מכירות ממקורות נוספים, וכל הנתונים מתרכזים במקום אחד ומוכנים לניתוח.</p>
            <Link to="/signup" className="text-link">פותחים חשבון ומתחילים <ArrowLeft size={18} aria-hidden="true" /></Link>
          </div>
        </section>

        <section className="public-section faq-section" id="faq">
          <div>
            <span className="eyebrow">לפני שמתחילים</span>
            <h2>שאלות טובות.<br />תשובות פשוטות.</h2>
          </div>
          <div className="faq-list">
            {faq.map(([question, answer]) => (
              <details key={question}><summary>{question}<ChevronDown size={18} aria-hidden="true" /></summary><p>{answer}</p></details>
            ))}
          </div>
        </section>

        <section className="public-cta">
          <span className="eyebrow">פחות סימני שאלה</span>
          <h2>הצעד הבא של העסק<br />מתחיל בתמונה ברורה.</h2>
          <Link to="/signup" className="public-button on-dark">פתיחת חשבון <ArrowLeft size={18} aria-hidden="true" /></Link>
        </section>
      </main>

      <footer className="public-footer">
        <PublicBrand />
        <span>© {new Date().getFullYear()} Sydney · מנהל הכנסות</span>
        <Link to="/login">כבר יש חשבון? מתחברים</Link>
      </footer>
    </div>
  )
}
