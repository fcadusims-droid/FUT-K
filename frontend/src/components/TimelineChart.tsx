// Momentum over the match: a single 2px line (HOME's share of recent momentum,
// 0..1) against a hairline 50% baseline, goal markers as >=8px team-colored dots
// with a 2px surface ring. Crosshair + one tooltip reading out every value at
// the hovered minute (interaction.md); clicking seeks the replay. The table
// view twin lives in ReplayView, so no value is gated behind hover.

import { useMemo, useRef, useState } from 'react'
import type { MatchDetail, PanelState } from '../types'

interface Props {
  timeline: PanelState[]
  detail: MatchDetail
  minute: number
  onSeek: (minute: number) => void
  homeName: string
  awayName: string
}

const W = 900
const H = 180
const PAD = { left: 36, right: 12, top: 12, bottom: 24 }

export function TimelineChart({ timeline, detail, minute, onSeek, homeName, awayName }: Props) {
  const [hover, setHover] = useState<PanelState | null>(null)
  const svgRef = useRef<SVGSVGElement>(null)

  const maxMin = timeline.length ? timeline[timeline.length - 1].minute : 90
  const x = (m: number) => PAD.left + ((W - PAD.left - PAD.right) * m) / maxMin
  const y = (v: number) => PAD.top + (H - PAD.top - PAD.bottom) * (1 - v)

  const path = useMemo(
    () =>
      timeline
        .map((p, i) => `${i === 0 ? 'M' : 'L'}${x(p.minute).toFixed(1)},${y(p.momentum.home).toFixed(1)}`)
        .join(' '),
    [timeline, maxMin],
  )

  const nearest = (clientX: number): PanelState | null => {
    const svg = svgRef.current
    if (!svg || !timeline.length) return null
    const rect = svg.getBoundingClientRect()
    const mx = ((clientX - rect.left) / rect.width) * W
    const m = ((mx - PAD.left) / (W - PAD.left - PAD.right)) * maxMin
    return timeline.reduce((best, p) =>
      Math.abs(p.minute - m) < Math.abs(best.minute - m) ? p : best,
    )
  }

  return (
    <div style={{ position: 'relative' }}>
      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>
        Momentum through the match — {homeName} share (goals marked)
      </div>
      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`}
        style={{ width: '100%', display: 'block', background: 'var(--surface-1)', borderRadius: 8 }}
        onPointerMove={(e) => setHover(nearest(e.clientX))}
        onPointerLeave={() => setHover(null)}
        onClick={(e) => {
          const p = nearest(e.clientX)
          if (p) onSeek(p.minute)
        }}
      >
        {/* recessive hairline grid: 0 / 50% / 100% */}
        {[0, 0.5, 1].map((v) => (
          <g key={v}>
            <line x1={PAD.left} x2={W - PAD.right} y1={y(v)} y2={y(v)} stroke="var(--gridline)" strokeWidth={1} />
            <text x={PAD.left - 6} y={y(v) + 4} textAnchor="end" fontSize={10} fill="var(--text-muted)">
              {v * 100}%
            </text>
          </g>
        ))}

        {/* momentum line: 2px, round joins, HOME hue */}
        <path d={path} fill="none" stroke="var(--home)" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />

        {/* goal markers: >=8px dots, team hue, 2px surface ring */}
        {detail.goal_minutes.map((g, i) => {
          const p = timeline.reduce((best, q) =>
            Math.abs(q.minute - g.minute) < Math.abs(best.minute - g.minute) ? q : best,
          )
          return (
            <circle
              key={`${g.minute}-${i}`}
              cx={x(g.minute)}
              cy={y(p.momentum.home)}
              r={5}
              fill={g.team === 'HOME' ? 'var(--home)' : 'var(--away)'}
              stroke="var(--surface-1)"
              strokeWidth={2}
            />
          )
        })}

        {/* replay cursor */}
        <line x1={x(minute)} x2={x(minute)} y1={PAD.top} y2={H - PAD.bottom} stroke="var(--baseline)" strokeWidth={1.5} />

        {/* crosshair */}
        {hover && (
          <line x1={x(hover.minute)} x2={x(hover.minute)} y1={PAD.top} y2={H - PAD.bottom} stroke="var(--text-muted)" strokeWidth={1} />
        )}

        {/* x ticks */}
        {[0, 15, 30, 45, 60, 75, 90].filter((m) => m <= maxMin).map((m) => (
          <text key={m} x={x(m)} y={H - 8} textAnchor="middle" fontSize={10} fill="var(--text-muted)">
            {m}'
          </text>
        ))}
      </svg>

      {hover && (
        <div
          style={{
            position: 'absolute',
            top: 24,
            left: `${(x(hover.minute) / W) * 100}%`,
            transform: `translateX(${hover.minute > maxMin / 2 ? '-105%' : '8px'})`,
            background: 'var(--surface-1)',
            border: '1px solid var(--border)',
            borderRadius: 8,
            padding: '8px 10px',
            fontSize: 12,
            pointerEvents: 'none',
            boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
            whiteSpace: 'nowrap',
          }}
        >
          <div style={{ color: 'var(--text-muted)', marginBottom: 2 }}>minute {Math.round(hover.minute)}</div>
          <div>
            <strong>{Math.round(hover.momentum.home * 100)}%</strong>{' '}
            <span style={{ borderBottom: '2px solid var(--home)' }}>{homeName}</span>
            {' · '}
            <strong>{Math.round(hover.momentum.away * 100)}%</strong>{' '}
            <span style={{ borderBottom: '2px solid var(--away)' }}>{awayName}</span>
          </div>
          <div style={{ color: 'var(--text-secondary)' }}>
            {hover.score.home}–{hover.score.away} · {hover.regime} ·{' '}
            <strong>{Math.round(hover.predictions.goal_next_10min * 100)}%</strong> goal in 10
          </div>
        </div>
      )}
    </div>
  )
}
