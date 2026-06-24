'use client'
import { useEffect, useState } from 'react'
import { api, DEMO_TENANT_ID } from '@/lib/api'
import type { AuditEntry } from '@/lib/types'

const STATUS_COLORS: Record<string, string> = {
  passed: 'text-green-400',
  blocked: 'text-red-400',
  flagged: 'text-amber-400',
  error: 'text-red-300',
}

export function AuditTail({ tenantId = DEMO_TENANT_ID }: { tenantId?: string }) {
  const [entries, setEntries] = useState<AuditEntry[]>([])

  useEffect(() => {
    const load = () =>
      api.audit.list(tenantId, 50).then((e) => setEntries(e as AuditEntry[])).catch(() => {})
    load()
    const id = setInterval(load, 5000)
    return () => clearInterval(id)
  }, [tenantId])

  return (
    <div className="bg-sentinel-panel border border-sentinel-border rounded-lg overflow-hidden mt-4">
      <div className="px-4 py-2 border-b border-sentinel-border">
        <h3 className="text-xs text-slate-400 font-medium uppercase tracking-wider">Audit Tail</h3>
      </div>
      <div className="overflow-y-auto max-h-48 font-mono text-xs p-2 space-y-0.5">
        {entries.length === 0 && <span className="text-slate-600">No audit entries yet…</span>}
        {entries.map((e) => (
          <div key={e.id} className="flex gap-3">
            <span className="text-slate-600 shrink-0">{e.created_at?.slice(11, 19)}</span>
            <span className={`${STATUS_COLORS[e.status] || 'text-slate-400'} shrink-0`}>{e.status}</span>
            <span className="text-slate-400">L{e.layer}</span>
            <span className="text-slate-300">{e.action}</span>
            <span className="text-slate-600 truncate">{e.request_id?.slice(0, 8)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
