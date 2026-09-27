import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'

import { BILLING_QUERY_KEY, getBillingOverview } from '../services/billingService'

/**
 * The business's subscription as the server sees it. Refreshed every few
 * minutes (trial days tick down) and immediately whenever an API call answers
 * 402, so a lockout is explained the moment it happens.
 */
export function useBillingOverview({ poll }: { poll?: number | false } = {}) {
  const queryClient = useQueryClient()
  useEffect(() => {
    const refresh = () => void queryClient.invalidateQueries({ queryKey: BILLING_QUERY_KEY })
    window.addEventListener('sydney:subscription-required', refresh)
    return () => window.removeEventListener('sydney:subscription-required', refresh)
  }, [queryClient])
  return useQuery({
    queryKey: BILLING_QUERY_KEY,
    queryFn: getBillingOverview,
    staleTime: 60_000,
    refetchInterval: poll || 5 * 60_000,
    retry: 1,
  })
}
