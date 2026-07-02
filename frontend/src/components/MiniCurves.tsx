// Analyst-mode signature visuals: Pressure Index (both teams) and the
// Confidence Curve, sharing the match x-axis. Thin 2px lines, hairline grid.

import type { PanelState } from '../types'

interface Props {
  timeline: PanelState[]
  homeName: string
  awayName: string
}

const W = 900
const H = 110
const PAD = { left: 36, right: 12, top: 14, bottom: 18 }

function path(timeline: PanelState[], maxMin: number, value: (p: PanelState) => number, maxV: number) {
  const x = (m: number) => PAD.left + ((W - PAD.left - PAD.right) * m) / maxMin
  const y = (v: number) => PAD.top + (H - PAD.top - PAD.bottom) * (1 - Math.min(1, v / maxV))
  return timeline
    .map((p, i) => `${i === 0 ? 'M' : 'L'}${x(p.minute).toFixed(1)},${y(value(p)).toFixed(1)}`)
    .join(' ')
}

function Chart({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginTop: 10 }}>
      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 2 }}>{title}</div>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', display: 'block' }}>
        <line x1={PAD.left} x2={W - PAD.right} y1={H - PAD.bottom} y2={H - PAD.bottom}
          stroke="var(--gridline)" strokeWidth={1} />
        {children}
      </svg>
    </div>
  )
}

export function MiniCurves({ timeline, homeName, awayName }: Props) {
  if (!timeline.length) return null
  const maxMin = timeline[timeline.length - 1].minute
  const maxPressure = Math.max(0.1, ...timeline.map((p) => Math.max(p.pressure.home, p.pressure.away)))

  return (
    <div>
      <Chart title={`Pressure Index — ${homeName} vs ${awayName}`}>
        <path d={path(timeline, maxMin, (p) => p.pressure.home, maxPressure)} fill="none"
          stroke="var(--home)" strokeWidth={2} strokeLinejoin="round" />
        <path d={path(timeline, maxMin, (p) => p.pressure.away, maxPressure)} fill="none"
          stroke="var(--away)" strokeWidth={2} strokeLinejoin="round" />
        <text x={W - PAD.right} y={PAD.top} textAnchor="end" fontSize={10} fill="var(--text-muted)">
          {homeName} / {awayName}
        </text>
      </Chart>
      <Chart title="Confidence Curve — how much the engine trusts its own reading">
        <path d={path(timeline, maxMin, (p) => p.confidence, 1)} fill="none"
          stroke="var(--baseline)" strokeWidth={2} strokeLinejoin="round" />
      </Chart>
    </div>
  )
}
