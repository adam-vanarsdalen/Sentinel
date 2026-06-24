'use client'
import { useEffect, useState, useCallback } from 'react'
import { api, DEMO_TENANT_ID } from '@/lib/api'
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
  const [resuming, setResuming] = useState<Record<string, boolean>>({})

  const loadAgents = useCallback(() => {
    api.agents.list(DEMO_TENANT_ID).then((data) => {
      const seen = new Set<string>()
      const unique = (data as Agent[]).filter((a) => {
        if (seen.has(a.name)) return false
        seen.add(a.name)
        return true
      })
      setAgents(unique)
    }).catch(() => {})
  }, [])

  // Initial load + poll every 5s to pick up auto-pauses
  useEffect(() => {
    loadAgents()
    const id = setInterval(loadAgents, 5000)
    return () => clearInterval(id)
  }, [loadAgents])

  async function handleResume(agent: Agent) {
    setResuming((prev) => ({ ...prev, [agent.id]: true }))
    try {
      await api.killSwitch.resume(
        agent.id,
        'dashboard',
        'Reviewed and approved — resuming from dashboard',
      )
      setAgents((prev) =>
        prev.map((a) => (a.id === agent.id ? { ...a, state: 'active' } : a))
      )
    } catch {
      // reload to get true server state on failure
      loadAgents()
    } finally {
      setResuming((prev) => ({ ...prev, [agent.id]: false }))
    }
  }

  return (
    <div>
      <h2 className="text-lg font-semibold text-slate-200 mb-4">Agents</h2>
      <div className="grid grid-cols-2 gap-4">
        {agents.length === 0 && (
          <p className="text-slate-500 text-sm col-span-2">
            No agents registered. Run <code className="text-sentinel-purple-light">seed_demo.py</code> to get started.
          </p>
        )}
        {agents.map((agent) => {
          const needsReview = agent.state === 'paused' || agent.state === 'terminated'
          const isResuming = resuming[agent.id]
          return (
            <div
              key={agent.id}
              className={clsx(
                'bg-sentinel-panel border rounded-lg p-4',
                needsReview ? 'border-orange-700' : 'border-sentinel-border',
              )}
            >
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

              {needsReview && (
                <div className="mt-3 pt-3 border-t border-orange-900/50">
                  <p className="text-xs text-orange-400 mb-2">Awaiting human review</p>
                  <button
                    onClick={() => handleResume(agent)}
                    disabled={isResuming}
                    className={clsx(
                      'w-full text-xs font-medium py-1.5 px-3 rounded transition-colors',
                      isResuming
                        ? 'bg-slate-700 text-slate-500 cursor-not-allowed'
                        : 'bg-green-800 hover:bg-green-700 text-green-200 cursor-pointer',
                    )}
                  >
                    {isResuming ? 'Resuming…' : 'Resume Agent'}
                  </button>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
