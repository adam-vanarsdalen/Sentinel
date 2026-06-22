import type { DashboardMetrics } from '@/lib/types'

interface Props { metrics: DashboardMetrics | null }

const CARDS = [
  { key: 'total_requests', label: 'Total Requests', color: 'text-blue-400' },
  { key: 'blocked_requests', label: 'Blocked (L3)', color: 'text-red-400' },
  { key: 'anomalies_flagged', label: 'Anomalies (L6)', color: 'text-sentinel-purple-light' },
  { key: 'compliance_packages', label: 'Compliance Pkgs (L7)', color: 'text-green-400' },
] as const

export function MetricCards({ metrics }: Props) {
  return (
    <div className="grid grid-cols-4 gap-4 mb-6">
      {CARDS.map(({ key, label, color }) => (
        <div key={key} className="bg-sentinel-panel border border-sentinel-border rounded-lg p-4">
          <div className={`text-3xl font-bold ${color}`}>
            {metrics ? (metrics[key] as number).toLocaleString() : '—'}
          </div>
          <div className="text-slate-400 text-xs mt-1">{label}</div>
        </div>
      ))}
    </div>
  )
}
