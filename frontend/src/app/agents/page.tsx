'use client'
import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import type { Agent } from '@/lib/types'
import clsx from 'clsx'

const STATE_COLORS: Record<string, string> = {
  active: 'bg-green-900 text-green-300',
  throttled: 'bg-amber-900 text-amber-300',
  paused: 'bg-orange-900 text-orange-300',
  terminated: 'bg-red-900 text-red-300',
}

export default function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([])
  const tenantId = 'default'

  useEffect(() => {
    api.agents.list(tenantId).then((a) => setAgents(a as Agent[])).catch(() => {})
  }, [])

  return (
    <div>
      <h2 className="text-lg font-semibold text-slate-200 mb-4">Agents</h2>
      <div className="grid grid-cols-2 gap-4">
        {agents.length === 0 && (
          <p className="text-slate-500 text-sm col-span-2">No agents registered. Run <code className="text-sentinel-purple-light">seed_demo.py</code> to get started.</p>
        )}
        {agents.map((agent) => (
          <div key={agent.id} className="bg-sentinel-panel border border-sentinel-border rounded-lg p-4">
            <div className="flex justify-between items-start mb-2">
              <div>
                <div className="text-slate-200 font-medium">{agent.name}</div>
                <div className="text-slate-500 text-xs font-mono mt-0.5">{agent.id.slice(0, 8)}…</div>
              </div>
              <span className={clsx('px-2 py-0.5 rounded text-xs font-medium', STATE_COLORS[agent.state])}>
                {agent.state}
              </span>
            </div>
            {agent.purpose_binding && (
              <div className="text-xs text-slate-400 mt-2">
                <span className="text-slate-500">Purpose:</span> {agent.purpose_binding}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
