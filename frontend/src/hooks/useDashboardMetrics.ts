'use client'
import { useEffect, useState } from 'react'
import { api, DEMO_TENANT_ID } from '@/lib/api'
import type { DashboardMetrics } from '@/lib/types'

export function useDashboardMetrics(tenantId = DEMO_TENANT_ID) {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null)

  useEffect(() => {
    const load = () => api.dashboard.metrics(tenantId).then((m) => setMetrics(m as DashboardMetrics)).catch(() => {})
    load()
    const id = setInterval(load, 5000)
    return () => clearInterval(id)
  }, [tenantId])

  return metrics
}
