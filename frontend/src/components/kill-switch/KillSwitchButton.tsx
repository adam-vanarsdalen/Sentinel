'use client'
import { useState } from 'react'
import { api } from '@/lib/api'

type Phase = 'idle' | 'armed' | 'firing' | 'done'

export function KillSwitchButton({ agentId = 'all' }: { agentId?: string }) {
  const [phase, setPhase] = useState<Phase>('idle')
  const [error, setError] = useState<string | null>(null)

  async function handleClick() {
    if (phase === 'idle') {
      setPhase('armed')
      return
    }
    if (phase === 'armed') {
      setPhase('firing')
      try {
        await api.killSwitch.fire(agentId, 'dashboard-operator', 'Manual kill switch via dashboard')
        setPhase('done')
        setTimeout(() => setPhase('idle'), 3000)
      } catch (e) {
        setError(String(e))
        setPhase('idle')
      }
    }
  }

  if (phase === 'done') {
    return (
      <span className="px-3 py-1.5 rounded text-xs bg-green-900 text-green-300 font-medium">
        Terminated
      </span>
    )
  }

  return (
    <div className="flex items-center gap-2">
      {error && <span className="text-red-400 text-xs">{error}</span>}
      <button
        onClick={handleClick}
        className={
          phase === 'armed'
            ? 'px-3 py-1.5 rounded text-xs font-bold bg-red-600 text-white animate-pulse'
            : phase === 'firing'
            ? 'px-3 py-1.5 rounded text-xs bg-red-900 text-red-300 cursor-not-allowed'
            : 'px-3 py-1.5 rounded text-xs bg-sentinel-border text-slate-300 hover:bg-red-900 hover:text-red-300 transition-colors'
        }
        disabled={phase === 'firing'}
      >
        {phase === 'idle' && 'Kill Switch'}
        {phase === 'armed' && '⚠ Confirm Fire'}
        {phase === 'firing' && 'Firing...'}
      </button>
      {phase === 'armed' && (
        <button
          onClick={() => setPhase('idle')}
          className="px-2 py-1.5 rounded text-xs text-slate-400 hover:text-slate-200"
        >
          Cancel
        </button>
      )}
    </div>
  )
}
