'use client'
import { useEffect, useState } from 'react'
import { api, DEMO_TENANT_ID } from '@/lib/api'
import type { AuditEntry } from '@/lib/types'

const ACTION_LABELS: Record<string, string> = {
  pipeline_complete: 'Pipeline Complete',
  request_blocked: 'Request Blocked',
  kill_switch_transition: 'Kill Switch',
  tool_call_blocked: 'Tool Blocked',
  human_review_escalated: 'Escalated',
}

const REG_SHORT: Record<string, string> = {
  EU_AI_ACT: 'EU AI Act',
  NIST_AI_RMF: 'NIST',
  COLORADO_SB205: 'CO SB205',
  HIPAA: 'HIPAA',
}

function formatTime(iso: string): string {
  const d = new Date(iso)
  const now = Date.now()
  const diff = Math.floor((now - d.getTime()) / 1000)
  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return d.toLocaleDateString()
}

export default function AuditPage() {
  const [entries, setEntries] = useState<AuditEntry[]>([])

  useEffect(() => {
    api.audit.list(DEMO_TENANT_ID, 200).then((e) => setEntries(e as AuditEntry[])).catch(() => {})
  }, [])

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-slate-200">Audit Log</h2>
        <a
          href={`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/audit/export/csv?tenant_id=${DEMO_TENANT_ID}`}
          className="text-xs text-sentinel-purple-light hover:underline"
        >
          Export CSV
        </a>
      </div>
      <div className="bg-sentinel-panel border border-sentinel-border rounded-lg overflow-hidden">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-sentinel-border text-slate-500">
              <th className="text-left px-3 py-2 w-12">ID</th>
              <th className="text-left px-3 py-2 w-24">Time</th>
              <th className="text-left px-3 py-2">Action</th>
              <th className="text-left px-3 py-2 w-12">Layer</th>
              <th className="text-left px-3 py-2 w-16">Status</th>
              <th className="text-left px-3 py-2">Regulations</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((e) => (
              <tr key={e.id} className="border-b border-sentinel-border/50 hover:bg-sentinel-border/20">
                <td className="px-3 py-1.5 font-mono text-slate-600">{e.id}</td>
                <td className="px-3 py-1.5 text-slate-500 whitespace-nowrap">
                  {e.created_at ? formatTime(e.created_at) : '—'}
                </td>
                <td className="px-3 py-1.5 text-slate-300">
                  {ACTION_LABELS[e.action] ?? e.action}
                </td>
                <td className="px-3 py-1.5 text-slate-400">L{e.layer}</td>
                <td className="px-3 py-1.5">
                  <span className={
                    e.status === 'passed' ? 'text-green-400' :
                    e.status === 'blocked' ? 'text-red-400' : 'text-amber-400'
                  }>
                    {e.status}
                  </span>
                </td>
                <td className="px-3 py-1.5">
                  <div className="flex flex-wrap gap-1">
                    {Object.entries(e.regulation_mappings || {}).map(([reg, controls]) => (
                      <span
                        key={reg}
                        title={`${reg}: ${(controls as string[]).join(', ')}`}
                        className="px-1.5 py-0.5 rounded bg-sentinel-border text-slate-400 text-[10px] whitespace-nowrap"
                      >
                        {REG_SHORT[reg] ?? reg}
                      </span>
                    ))}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
