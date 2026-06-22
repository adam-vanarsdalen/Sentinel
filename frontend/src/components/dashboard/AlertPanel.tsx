'use client'
import { useAlerts } from '@/hooks/useAlerts'
import clsx from 'clsx'

const SEVERITY_COLORS: Record<string, string> = {
  critical: 'border-red-500 bg-red-950/40 text-red-300',
  high: 'border-orange-500 bg-orange-950/40 text-orange-300',
  medium: 'border-amber-500 bg-amber-950/40 text-amber-300',
  low: 'border-slate-500 bg-slate-900/40 text-slate-300',
}

export function AlertPanel() {
  const { messages: alerts, connected } = useAlerts()

  return (
    <div className="bg-sentinel-panel border border-sentinel-border rounded-lg w-72 shrink-0 flex flex-col">
      <div className="px-4 py-2 border-b border-sentinel-border flex justify-between items-center">
        <h3 className="text-xs text-slate-400 font-medium uppercase tracking-wider">Alerts</h3>
        <span className={clsx('w-2 h-2 rounded-full', connected ? 'bg-green-500' : 'bg-red-500')} />
      </div>
      <div className="overflow-y-auto flex-1 p-3 space-y-2 max-h-96">
        {alerts.length === 0 && (
          <p className="text-slate-600 text-xs text-center py-4">No alerts</p>
        )}
        {alerts.slice(0, 30).map((alert, i) => (
          <div key={i} className={clsx('border rounded p-2 text-xs', SEVERITY_COLORS[(alert as any).severity] || SEVERITY_COLORS.low)}>
            <div className="font-medium">{(alert as any).type || (alert as any).alert_type || 'event'}</div>
            <div className="mt-0.5 opacity-75">{(alert as any).message || (alert as any).reason || JSON.stringify(alert).slice(0, 80)}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
