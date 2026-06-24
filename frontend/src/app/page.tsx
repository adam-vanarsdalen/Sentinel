'use client'
import { MetricCards } from '@/components/dashboard/MetricCards'
import { ThroughputChart } from '@/components/dashboard/ThroughputChart'
import { RequestFeed } from '@/components/dashboard/RequestFeed'
import { AlertPanel } from '@/components/dashboard/AlertPanel'
import { AuditTail } from '@/components/dashboard/AuditTail'
import { useDashboardMetrics } from '@/hooks/useDashboardMetrics'

export default function DashboardPage() {
  const metrics = useDashboardMetrics()

  return (
    <div className="space-y-0">
      <MetricCards metrics={metrics} />
      <div className="flex gap-4">
        <div className="flex-1 min-w-0">
          <ThroughputChart />
          <RequestFeed />
        </div>
        <AlertPanel />
      </div>
      <AuditTail />
    </div>
  )
}
