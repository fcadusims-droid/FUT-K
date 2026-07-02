// Passing network (Section 12, Layer 5): circular-layout SVG graph.
// Node size = involvement; edge width = passes; edges that created chances
// use the team hue. Team toggle; loaded lazily when the card opens.

import { useEffect, useState } from 'react'

interface Node { id: string; name: string; label: string; strength: number }
interface Edge { from: string; to: string; passes: number; chances: number }
interface Net {
  team: string; side: string; nodes: Node[]; edges: Edge[]
  robustness: number; dependence: number
}

const W = 640
const H = 480
const CX = W / 2
const CY = H / 2 + 8
const R = 180

export function NetworkView({ matchId, homeName, awayName }: {
  matchId: string; homeName: string; awayName: string
}) {
  const [side, setSide] = useState<'HOME' | 'AWAY'>('HOME')
  const [net, setNet] = useState<Net | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setNet(null)
    fetch(`/api/matches/${matchId}/network?side=${side}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`${r.status}`))))
      .then(setNet)
      .catch((e) => setError(String(e)))
  }, [matchId, side])

  if (error) {
    return <p style={{ color: 'var(--text-secondary)' }}>Network unavailable ({error}).</p>
  }
  if (!net) return <p style={{ color: 'var(--text-muted)' }}>Loading network…</p>

  const pos = new Map(
    net.nodes.map((n, i) => {
      const a = (2 * Math.PI * i) / net.nodes.length - Math.PI / 2
      return [n.id, { x: CX + R * Math.cos(a), y: CY + R * Math.sin(a) }] as const
    }),
  )
  const maxS = Math.max(...net.nodes.map((n) => n.strength), 1)
  const maxP = Math.max(...net.edges.map((e) => e.passes), 1)
  const hue = side === 'HOME' ? 'var(--home)' : 'var(--away)'

  return (
    <div>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8 }}>
        <button className={side === 'HOME' ? 'primary' : ''} onClick={() => setSide('HOME')}>
          {homeName}
        </button>
        <button className={side === 'AWAY' ? 'primary' : ''} onClick={() => setSide('AWAY')}>
          {awayName}
        </button>
        <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>
          robustness {net.robustness} · dependence {net.dependence}
        </span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', display: 'block' }}>
        {net.edges.map((e, i) => {
          const a = pos.get(e.from)
          const b = pos.get(e.to)
          if (!a || !b) return null
          return (
            <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y}
              stroke={e.chances > 0 ? hue : 'var(--baseline)'}
              strokeOpacity={e.chances > 0 ? 0.9 : 0.45}
              strokeWidth={Math.max(1, (e.passes / maxP) * 7)}>
              <title>{`${e.passes} passes${e.chances ? ` · ${e.chances} chance(s)` : ''}`}</title>
            </line>
          )
        })}
        {net.nodes.map((n) => {
          const p = pos.get(n.id)!
          const r = 6 + (n.strength / maxS) * 10
          const outside = p.y < CY ? -r - 6 : r + 14
          return (
            <g key={n.id}>
              <circle cx={p.x} cy={p.y} r={r} fill={hue}
                stroke="var(--surface-1)" strokeWidth={2}>
                <title>{`${n.name} — ${n.strength} pass involvements`}</title>
              </circle>
              <text x={p.x} y={p.y + outside} textAnchor="middle" fontSize={11}
                fill="var(--text-secondary)">{n.label}</text>
            </g>
          )
        })}
      </svg>
      <p style={{ color: 'var(--text-muted)', fontSize: 12, margin: '6px 0 0' }}>
        Node size = pass involvement · line width = passes between the pair ·
        colored lines created chances.
      </p>
    </div>
  )
}
