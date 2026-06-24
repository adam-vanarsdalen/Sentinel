const LAYERS = [
  { n: 1, name: 'Ingestion', diff: false },
  { n: 2, name: 'Routing', diff: false },
  { n: 3, name: 'Enforcement', diff: true },
  { n: 4, name: 'Reasoning', diff: false },
  { n: 5, name: 'Grounding', diff: false },
  { n: 6, name: 'Anomaly', diff: true },
  { n: 7, name: 'Compliance', diff: true },
]

export function LayerHealth({ throughputs = {} }: { throughputs?: Record<number, number> }) {
  return (
    <div className="bg-sentinel-panel border border-sentinel-border rounded-lg p-4 w-52 shrink-0">
      <h3 className="text-xs text-slate-400 font-medium uppercase tracking-wider mb-3">Layer Health</h3>
      <div className="space-y-2">
        {LAYERS.map(({ n, name, diff }) => {
          const rps = throughputs[n] ?? 0
          const pct = Math.min((rps / 100) * 100, 100)
          return (
            <div key={n}>
              <div className="flex justify-between text-xs mb-0.5">
                <span className={diff ? 'text-sentinel-purple-light font-medium' : 'text-slate-300'}>
                  L{n}: {name}
                  {diff && ' ★'}
                </span>
                <span className="text-slate-500">{rps > 0 ? `${rps}/s` : '—'}</span>
              </div>
              <div className="h-1.5 bg-sentinel-border rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${diff ? 'bg-sentinel-purple' : 'bg-blue-600'}`}
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
