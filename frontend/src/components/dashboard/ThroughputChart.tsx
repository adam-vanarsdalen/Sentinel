'use client'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { useEffect, useState } from 'react'

interface DataPoint { t: string; rps: number }

export function ThroughputChart({ rps = 0 }: { rps?: number }) {
  const [data, setData] = useState<DataPoint[]>([])

  useEffect(() => {
    const tick = () => {
      const now = new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
      setData((prev) => [...prev.slice(-29), { t: now, rps }])
    }
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [rps])

  return (
    <div className="bg-sentinel-panel border border-sentinel-border rounded-lg p-4 mb-4">
      <h3 className="text-xs text-slate-400 font-medium uppercase tracking-wider mb-3">Throughput (30s)</h3>
      <ResponsiveContainer width="100%" height={120}>
        <AreaChart data={data}>
          <defs>
            <linearGradient id="rpsGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#7C3AED" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#7C3AED" stopOpacity={0} />
            </linearGradient>
          </defs>
          <XAxis dataKey="t" tick={{ fontSize: 10, fill: '#64748B' }} interval="preserveStartEnd" />
          <YAxis tick={{ fontSize: 10, fill: '#64748B' }} width={30} />
          <Tooltip contentStyle={{ background: '#1A1A2E', border: '1px solid #2D2D4A', fontSize: 11 }} />
          <Area type="monotone" dataKey="rps" stroke="#7C3AED" fill="url(#rpsGrad)" strokeWidth={2} dot={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
