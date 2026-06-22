'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import clsx from 'clsx'

const NAV = [
  { href: '/', label: 'Dashboard' },
  { href: '/agents', label: 'Agents' },
  { href: '/policies', label: 'Policies' },
  { href: '/audit', label: 'Audit Log' },
  { href: '/compliance', label: 'Compliance' },
]

export function Sidebar() {
  const path = usePathname()
  return (
    <aside className="w-52 bg-sentinel-panel border-r border-sentinel-border flex flex-col shrink-0">
      <div className="p-4 border-b border-sentinel-border">
        <span className="text-sentinel-purple-light font-bold text-lg tracking-wide">SENTINEL</span>
        <span className="text-slate-500 text-xs block">AI Governance</span>
      </div>
      <nav className="flex-1 p-3 space-y-1">
        {NAV.map(({ href, label }) => (
          <Link
            key={href}
            href={href}
            className={clsx(
              'block px-3 py-2 rounded text-sm transition-colors',
              path === href
                ? 'bg-sentinel-purple text-white'
                : 'text-slate-400 hover:text-white hover:bg-sentinel-border'
            )}
          >
            {label}
          </Link>
        ))}
      </nav>
      <div className="p-3 text-xs text-slate-600 border-t border-sentinel-border">v1.0.0</div>
    </aside>
  )
}
