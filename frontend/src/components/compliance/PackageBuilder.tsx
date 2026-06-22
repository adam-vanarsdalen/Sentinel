'use client'
import { useState } from 'react'
import { api } from '@/lib/api'

const REGULATIONS = ['EU_AI_ACT', 'NIST_AI_RMF', 'COLORADO_SB205', 'HIPAA']

export function PackageBuilder() {
  const [start, setStart] = useState('2026-06-01T00:00:00')
  const [end, setEnd] = useState('2026-06-22T23:59:59')
  const [selected, setSelected] = useState<string[]>(REGULATIONS)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)

  function toggleReg(r: string) {
    setSelected((prev) => prev.includes(r) ? prev.filter((x) => x !== r) : [...prev, r])
  }

  async function generate() {
    setLoading(true)
    setError(null)
    try {
      const pkg = await api.compliance.generate({
        tenant_id: 'default',
        time_range_start: start,
        time_range_end: end,
        regulations: selected,
      })
      setResult(pkg)
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="bg-sentinel-panel border border-sentinel-border rounded-lg p-4 space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-xs text-slate-400 block mb-1">Start</label>
            <input
              type="datetime-local"
              value={start}
              onChange={(e) => setStart(e.target.value)}
              className="w-full bg-sentinel-border text-slate-200 text-sm px-3 py-1.5 rounded border border-sentinel-border focus:outline-none focus:border-sentinel-purple"
            />
          </div>
          <div>
            <label className="text-xs text-slate-400 block mb-1">End</label>
            <input
              type="datetime-local"
              value={end}
              onChange={(e) => setEnd(e.target.value)}
              className="w-full bg-sentinel-border text-slate-200 text-sm px-3 py-1.5 rounded border border-sentinel-border focus:outline-none focus:border-sentinel-purple"
            />
          </div>
        </div>
        <div>
          <label className="text-xs text-slate-400 block mb-2">Regulations</label>
          <div className="flex gap-3">
            {REGULATIONS.map((r) => (
              <label key={r} className="flex items-center gap-1.5 text-xs text-slate-300 cursor-pointer">
                <input type="checkbox" checked={selected.includes(r)} onChange={() => toggleReg(r)} className="accent-sentinel-purple" />
                {r}
              </label>
            ))}
          </div>
        </div>
        <button
          onClick={generate}
          disabled={loading || selected.length === 0}
          className="px-4 py-2 bg-sentinel-purple hover:bg-sentinel-purple/80 text-white text-sm rounded transition-colors disabled:opacity-50"
        >
          {loading ? 'Generating…' : 'Generate Package'}
        </button>
        {error && <p className="text-red-400 text-xs">{error}</p>}
      </div>

      {result && (
        <div className="bg-sentinel-panel border border-sentinel-border rounded-lg p-4 space-y-3">
          <div className="flex justify-between items-center">
            <h3 className="text-slate-200 font-medium text-sm">Package: {result.package_id?.slice(0, 8)}…</h3>
            <a
              href={`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/compliance/${result.package_id}/pdf`}
              target="_blank"
              rel="noreferrer"
              className="text-xs text-sentinel-purple-light hover:underline"
            >
              Download PDF
            </a>
          </div>
          <div className="grid grid-cols-4 gap-3 text-xs">
            {[
              ['Total Requests', result.total_requests],
              ['Blocked', result.blocked_requests],
              ['Anomalies', result.anomalies_detected],
              ['Kill Switch Events', result.kill_switch_events],
            ].map(([label, val]) => (
              <div key={label as string} className="bg-sentinel-border/50 rounded p-2">
                <div className="text-slate-400">{label}</div>
                <div className="text-slate-100 font-bold">{val ?? 0}</div>
              </div>
            ))}
          </div>
          {result.gap_analysis?.length > 0 && (
            <div>
              <h4 className="text-xs text-amber-400 font-medium mb-2">Gaps ({result.gap_analysis.length})</h4>
              <div className="space-y-1.5">
                {result.gap_analysis.slice(0, 10).map((gap: any, i: number) => (
                  <div key={i} className="text-xs bg-amber-950/30 border border-amber-900/50 rounded p-2">
                    <span className="text-amber-300 font-medium">{gap.regulation} — {gap.control_id}</span>
                    <p className="text-slate-400 mt-0.5">{gap.gap_description}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
