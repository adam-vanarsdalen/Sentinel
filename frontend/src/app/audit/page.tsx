'use client'
import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import type { AuditEntry } from '@/lib/types'

export default function AuditPage() {
  const [entries, setEntries] = useState<AuditEntry[]>([])
  const tenantId = 'default'

  useEffect(() => {
    api.audit.list(tenantId, 200).then((e) => setEntries(e as AuditEntry[])).catch(() => {})
  }, [])

  return (
    <div>
      <h2 className="text-lg font-semibold text-slate-200 mb-4">Audit Log</h2>
      <a
        href={`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/audit/export/csv?tenant_id=${tenantId}`}
        className="text-xs text-sentinel-purple-light hover:underline mb-4 inline-block"
      >
        Export CSV
      </a>
      <div className="bg-sentinel-panel border border-sentinel-border rounded-lg overflow-hidden">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-sentinel-border text-slate-500">
              <th className="text-left px-3 py-2">ID</th>
              <th className="text-left px-3 py-2">Time</th>
              <th className="text-left px-3 py-2">Action</th>
              <th className="text-left px-3 py-2">Layer</th>
              <th className="text-left px-3 py-2">Status</th>
              <th className="text-left px-3 py-2">Regulations</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((e) => (
              <tr key={e.id} className="border-b border-sentinel-border/50 hover:bg-sentinel-border/20">
                <td className="px-3 py-1.5 font-mono text-slate-500">{e.id}</td>
                <td className="px-3 py-1.5 text-slate-500">{e.created_at?.slice(0, 19)}</td>
                <td className="px-3 py-1.5 text-slate-300">{e.action}</td>
                <td className="px-3 py-1.5 text-slate-400">L{e.layer}</td>
                <td className="px-3 py-1.5">
                  <span className={e.status === 'passed' ? 'text-green-400' : e.status === 'blocked' ? 'text-red-400' : 'text-amber-400'}>
                    {e.status}
                  </span>
                </td>
                <td className="px-3 py-1.5 text-slate-500">
                  {Object.entries(e.regulation_mappings || {}).map(([reg, controls]) => (
                    <span key={reg} className="mr-2">{reg}: {(controls as string[]).join(', ')}</span>
                  ))}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
