import { useEffect, useRef } from 'react'

/** One-shot entrances; content stays visible when motion or observers are unavailable. */
export function useLandingMotion() {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const root = ref.current
    if (!root || !('IntersectionObserver' in window)) return
    const preference = window.matchMedia('(prefers-reduced-motion: reduce)')
    const targets = Array.from(root.querySelectorAll<HTMLElement>([
      '.hero-copy > *', '.hero-product', '.section-heading',
      '.feature-grid > article', '.steps > article',
      '.connection-section > div', '.faq-section > div', '.public-cta',
    ].join(', ')))
    let observer: IntersectionObserver | undefined
    const seen = new WeakSet<Element>()

    function configure() {
      observer?.disconnect()
      targets.forEach(target => {
        target.classList.remove('motion-enter')
        target.style.removeProperty('--enter-delay')
      })
      if (preference.matches) return

      targets.forEach(target => {
        const parent = target.parentElement
        if (parent?.matches('.hero-copy, .feature-grid, .steps')) {
          const index = Array.from(parent.children).indexOf(target)
          target.style.setProperty('--enter-delay', `${index * 80}ms`)
        }
      })
      observer = new IntersectionObserver(entries => {
        entries.forEach(entry => {
          if (!entry.isIntersecting) return
          if (!seen.has(entry.target)) {
            entry.target.classList.add('motion-enter')
            seen.add(entry.target)
          }
          observer?.unobserve(entry.target)
        })
      }, { threshold: 0.08 })
      targets.forEach(target => {
        if (!seen.has(target)) observer?.observe(target)
      })
    }

    configure()
    preference.addEventListener('change', configure)
    return () => {
      observer?.disconnect()
      preference.removeEventListener('change', configure)
      targets.forEach(target => {
        target.classList.remove('motion-enter')
        target.style.removeProperty('--enter-delay')
      })
    }
  }, [])

  return ref
}
