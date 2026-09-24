import { useEffect, useRef, useState } from 'react'

export function prefersReducedMotion(): boolean {
  return typeof window !== 'undefined' && typeof window.matchMedia === 'function'
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

/**
 * Eases from the previous value to a new one (e.g. after switching period).
 * The first render always shows the exact final value — a figure must never
 * be read mid-animation on arrival — and reduced motion disables tweening.
 */
export function useAnimatedNumber(target: number, durationMs = 450): number {
  const [value, setValue] = useState(target)
  const previous = useRef(target)

  useEffect(() => {
    const from = previous.current
    previous.current = target
    if (from === target || !Number.isFinite(from) || !Number.isFinite(target) || prefersReducedMotion()
      || typeof window.requestAnimationFrame !== 'function') {
      setValue(target)
      return
    }
    let frame = 0
    const start = performance.now()
    const tick = (now: number) => {
      const progress = Math.min(1, (now - start) / durationMs)
      const eased = 1 - (1 - progress) ** 4
      setValue(progress >= 1 ? target : from + (target - from) * eased)
      if (progress < 1) frame = window.requestAnimationFrame(tick)
    }
    frame = window.requestAnimationFrame(tick)
    return () => window.cancelAnimationFrame(frame)
  }, [target, durationMs])

  return value
}
