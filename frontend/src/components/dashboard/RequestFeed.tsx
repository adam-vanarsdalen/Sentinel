'use client'
import { useEffect, useState } from 'react'
import { useWebSocket } from '@/hooks/useWebSocket'
import { DEMO_TENANT_ID } from '@/lib/api'
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

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export function RequestFeed() {
  const [history, setHistory] = useState<RequestEvent[]>([])
  const { messages: liveEvents } = useWebSocket<RequestEvent>('/ws/requests')

  // Pre-populate from REST on mount
  useEffect(() => {
    fetch(`${API_BASE}/api/audit/?tenant_id=${DEMO_TENANT_ID}&limit=20`)
      .then((r) => r.json())
      .then((entries: any[]) => {
        const formatted: RequestEvent[] = entries
          .filter((e) => ['pipeline_complete', 'request_blocked'].includes(e.action))
          .map((e) => ({
            request_id: e.request_id,
            status: e.status ?? (e.action === 'request_blocked' ? 'blocked' : 'passed'),
            agent_id: e.agent_id ?? null,
            model: e.model ?? null,
            latency_ms: e.latency_ms ?? null,
            ts: e.created_at,
          }))
        setHistory(formatted)
      })
      .catch(() => {})
  }, [])

  // Merge live (newest first) + history, deduplicate by request_id, cap at 50
  const seen = new Set<string>()
  const allMessages: RequestEvent[] = []
  for (const r of [...liveEvents, ...history]) {
    if (!seen.has(r.request_id)) {
      seen.add(r.request_id)
      allMessages.push(r)
    }
    if (allMessages.length >= 50) break
  }

  return (
    <div className="bg-sentinel-panel border border-sentinel-border rounded-lg overflow-hidden">
      <div className="px-4 py-2 border-b border-sentinel-border flex justify-between">
        <h3 className="text-xs text-slate-400 font-medium uppercase tracking-wider">Live Requests</h3>
        <span className="text-xs text-slate-500">{allMessages.length} recent</span>
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
            {allMessages.length === 0 && (
              <tr><td colSpan={4} className="px-3 py-4 text-slate-600 text-center">No recent requests</td></tr>
            )}
            {allMessages.map((r, i) => (
              <tr key={r.request_id} className={clsx('border-b border-sentinel-border/50', i === 0 && 'row-new')}>
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
