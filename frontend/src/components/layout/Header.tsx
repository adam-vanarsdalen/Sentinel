'use client'
import { KillSwitchButton } from '@/components/kill-switch/KillSwitchButton'

export function Header() {
  return (
    <header className="h-14 bg-sentinel-panel border-b border-sentinel-border flex items-center justify-between px-6 shrink-0">
      <h1 className="text-slate-200 text-sm font-medium">Sentinel Stack</h1>
      <KillSwitchButton />
    </header>
  )
}
