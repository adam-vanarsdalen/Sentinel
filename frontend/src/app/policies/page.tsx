'use client'
import { useEffect, useState } from 'react'
import { api, DEMO_TENANT_ID } from '@/lib/api'

interface Policy {
  id: string
  name: string
  version: number
  action_limit_session: number
  allowed_models: string[]
  forbidden_endpoints: string[]
  forbidden_data_classes: string[]
  is_active: boolean
}

export default function PoliciesPage() {
  const [policies, setPolicies] = useState<Policy[]>([])

  useEffect(() => {
    fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/policies/?tenant_id=${DEMO_TENANT_ID}`)
      .then((r) => r.json())
      .then((data: Policy[]) => {
        // Deduplicate by name — keep first occurrence (latest from API ordering)
        const seen = new Set<string>()
        const unique = data.filter((p) => {
          if (seen.has(p.name)) return false
          seen.add(p.name)
          return true
        })
        setPolicies(unique)
      })
      .catch(() => {})
  }, [])

  return (
    <div>
      <h2 className="text-lg font-semibold text-slate-200 mb-4">Policies</h2>
      {policies.length === 0 ? (
        <p className="text-slate-500 text-sm">No policies found.</p>
      ) : (
        <div className="grid grid-cols-2 gap-4">
          {policies.map((p) => (
            <div key={p.id} className="bg-sentinel-panel border border-sentinel-border rounded-lg p-4 space-y-2">
              <div className="flex justify-between items-start">
                <div>
                  <div className="text-slate-200 font-medium">{p.name}</div>
                  <div className="text-slate-500 text-xs font-mono mt-0.5">{p.id.slice(0, 8)}…</div>
                </div>
                <span className={`px-2 py-0.5 rounded text-xs font-medium ${p.is_active ? 'bg-green-900 text-green-300' : 'bg-slate-700 text-slate-400'}`}>
                  {p.is_active ? 'active' : 'inactive'}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
                <div>
                  <span className="text-slate-500">Action limit:</span>{' '}
                  <span className="text-slate-300">{p.action_limit_session.toLocaleString()}/session</span>
                </div>
                <div>
                  <span className="text-slate-500">Version:</span>{' '}
                  <span className="text-slate-300">v{p.version}</span>
                </div>
              </div>
              {p.forbidden_data_classes.length > 0 && (
                <div className="text-xs">
                  <span className="text-slate-500">Forbidden data:</span>{' '}
                  <span className="text-amber-400">{p.forbidden_data_classes.join(', ')}</span>
                </div>
              )}
              {p.forbidden_endpoints.length > 0 && (
                <div className="text-xs">
                  <span className="text-slate-500">Blocked endpoints:</span>{' '}
                  <span className="text-amber-400">{p.forbidden_endpoints.join(', ')}</span>
                </div>
              )}
              {p.allowed_models.length > 0 && (
                <div className="text-xs">
                  <span className="text-slate-500">Allowed models:</span>{' '}
                  <span className="text-slate-300">{p.allowed_models.join(', ')}</span>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
