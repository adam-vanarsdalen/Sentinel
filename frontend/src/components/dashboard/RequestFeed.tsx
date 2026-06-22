'use client'
import { useWebSocket } from '@/hooks/useWebSocket'
import clsx from 'clsx'

interface RequestEvent {
  request_id: string
  status: string
  agent_id: string | null
  model: string | null
  latency_ms: number | null
  ts: string
}

const STATUS_COLORS: Record<string, string> = {
  passed: 'text-green-400 bg-green-900/30',
  blocked: 'text-red-400 bg-red-900/30',
  flagged: 'text-amber-400 bg-amber-900/30',
  error: 'text-red-300 bg-red-950/30',
}

export function RequestFeed() {
  const { messages } = useWebSocket<RequestEvent>('/ws/requests')

  return (
    <div className="bg-sentinel-panel border border-sentinel-border rounded-lg overflow-hidden">
      <div className="px-4 py-2 border-b border-sentinel-border flex justify-between">
        <h3 className="text-xs text-slate-400 font-medium uppercase tracking-wider">Live Requests</h3>
        <span className="text-xs text-slate-500">{messages.length} recent</span>
      </div>
      <div className="overflow-y-auto max-h-56">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-slate-500 border-b border-sentinel-border">
              <th className="text-left px-3 py-1.5">Status</th>
              <th className="text-left px-3 py-1.5">Request ID</th>
              <th className="text-left px-3 py-1.5">Agent</th>
              <th className="text-right px-3 py-1.5">Latency</th>
            </tr>
          </thead>
          <tbody>
            {messages.length === 0 && (
              <tr><td colSpan={4} className="px-3 py-4 text-slate-600 text-center">Waiting for requests…</td></tr>
            )}
            {messages.map((r, i) => (
              <tr key={r.request_id || i} className={clsx('border-b border-sentinel-border/50', i === 0 && 'row-new')}>
                <td className="px-3 py-1.5">
                  <span className={clsx('px-1.5 py-0.5 rounded text-xs font-medium', STATUS_COLORS[r.status] || 'text-slate-400')}>
                    {r.status?.toUpperCase()}
                  </span>
                </td>
                <td className="px-3 py-1.5 text-slate-400 font-mono">{r.request_id?.slice(0, 8)}…</td>
                <td className="px-3 py-1.5 text-slate-400">{r.agent_id?.slice(0, 8) || '—'}</td>
                <td className="px-3 py-1.5 text-slate-400 text-right">{r.latency_ms != null ? `${r.latency_ms}ms` : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
