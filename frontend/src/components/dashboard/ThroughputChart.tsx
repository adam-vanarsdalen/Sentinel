'use client'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { useEffect, useRef, useState } from 'react'
import { useWebSocket } from '@/hooks/useWebSocket'
import { DEMO_TENANT_ID } from '@/lib/api'

interface DataPoint { t: string; rps: number }
interface LiveMetrics { layer_throughputs: Record<string, number>; total_rps: number }

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

function timeStr(d = new Date()) {
  return d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function seedPoints(rps: number): DataPoint[] {
  const now = Date.now()
  return Array.from({ length: 30 }, (_, i) => ({
    t: timeStr(new Date(now - (29 - i) * 1000)),
    rps,
  }))
}

export function ThroughputChart() {
  const [data, setData] = useState<DataPoint[]>([])
  const currentRps = useRef(0)
  const { messages } = useWebSocket<LiveMetrics>('/ws/metrics')

  // Seed with historical rps on mount
  useEffect(() => {
    fetch(`${API_BASE}/api/dashboard/recent-rps?tenant_id=${DEMO_TENANT_ID}`)
      .then((r) => r.json())
      .then(({ rps }: { rps: number }) => {
        currentRps.current = rps
        setData(seedPoints(rps))
      })
      .catch(() => setData(seedPoints(0)))
  }, [])

  // Track latest rps from WebSocket
  useEffect(() => {
    if (messages.length > 0) {
      currentRps.current = messages[0].total_rps
    }
  }, [messages])

  // Tick every second
  useEffect(() => {
    const id = setInterval(() => {
      setData((prev) => [...prev.slice(-29), { t: timeStr(), rps: currentRps.current }])
    }, 1000)
    return () => clearInterval(id)
  }, [])

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
