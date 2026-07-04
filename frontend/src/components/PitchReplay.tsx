// The Digital Match Twin's living pitch (v2).
//
// When the dense twin stream is available, this animates the match as it
// actually happened: the ball follows every recorded pass, carry and shot —
// real start/end locations, real sub-second durations — and each player dot
// glides between that player's OWN recorded touch locations. Nothing is
// fabricated: every coordinate on screen is provider truth or an honest
// interpolation between two of that entity's real recorded positions.
//
// Without the stream (no raw cache), it falls back to the sparse normalized
// events — fewer touchpoints, same honesty.
//
// Modes: standard · tv (broadcast-minimal) · analysis (zones, momentum,
// commentary log).

import { useEffect, useMemo, useState } from 'react'
import { fetchExplain, fetchTactics } from '../api'
import { PlayerCard } from './PlayerCard'
import type {
  ExplainPayload, MatchEvent2D, PanelState, StoryBeat, TacticalGeometry, TwinItem,
} from '../types'

type Mode = 'standard' | 'tv' | 'analysis' | 'tactics'

// Lane centre in a team's own attacking y-frame (StatsBomb: high y = left).
const LANE_Y: Record<string, number> = { left: 74, central: 40, right: 6 }

interface Props {
  matchId: string
  events: MatchEvent2D[]           // sparse fallback + card pins
  twin: TwinItem[] | null          // dense stream (null -> fallback mode)
  panel: PanelState
  story: StoryBeat[] | null
  clock: number                    // match minutes, continuous
  playing: boolean
  homeName: string
  awayName: string
}

// ---------------------------------------------------------------------------
// Geometry: engine 0-100 frame (acting team attacks left->right) -> display
// 120x80 stadium frame where HOME always attacks right.
const px = (x: number, team: string) => (team === 'AWAY' ? 120 - x * 1.2 : x * 1.2)
const py = (y: number, team: string) => (team === 'AWAY' ? 80 - y * 0.8 : y * 0.8)
const lerp = (a: number, b: number, t: number) => a + (b - a) * t
const clamp01 = (t: number) => Math.max(0, Math.min(1, t))

interface Seg { t0: number; t1: number; x0: number; y0: number; x1: number; y1: number
                type: string; team: string; player: string | null; outcome?: string }
interface Track { t: number; x: number; y: number }

function lastIndexLE(arr: { t0?: number; t?: number }[], t: number): number {
  let lo = 0, hi = arr.length - 1, ans = -1
  while (lo <= hi) {
    const mid = (lo + hi) >> 1
    const v = (arr[mid] as { t0?: number; t?: number })
    if ((v.t0 ?? v.t ?? 0) <= t) { ans = mid; lo = mid + 1 } else hi = mid - 1
  }
  return ans
}

export function PitchReplay({
  matchId, events, twin, panel, story, clock, playing, homeName, awayName,
}: Props) {
  const [mode, setMode] = useState<Mode>('standard')
  const [why, setWhy] = useState<ExplainPayload | null>(null)
  const [whyBusy, setWhyBusy] = useState(false)
  const [selected, setSelected] = useState<{ id: string; name: string | null } | null>(null)
  const [tactics, setTactics] = useState<TacticalGeometry | null>(null)

  // Tactics layer: fetch the intelligent-field geometry when the whole-minute
  // changes (throttled — the geometry is a trailing-window read, not per-frame).
  const wholeMinute = Math.floor(clock)
  useEffect(() => {
    if (mode !== 'tactics') return
    let alive = true
    fetchTactics(matchId, wholeMinute)
      .then((g) => alive && setTactics(g))
      .catch(() => alive && setTactics(null))
    return () => { alive = false }
  }, [mode, matchId, wholeMinute])

  const T = clock * 60 // seconds on the match clock

  // ----- dense mode precomputation ----------------------------------------
  const segs: Seg[] = useMemo(() => {
    if (!twin) return []
    const out: Seg[] = []
    for (const it of twin) {
      if (it.x == null || it.y == null || it.x2 == null || it.y2 == null) continue
      const dur = Math.max(it.dur ?? 0, 0.25)
      out.push({
        t0: it.t, t1: it.t + dur,
        x0: px(it.x, it.team), y0: py(it.y, it.team),
        x1: px(it.x2, it.team), y1: py(it.y2, it.team),
        type: it.type, team: it.team, player: it.player, outcome: it.outcome,
      })
    }
    return out
  }, [twin])

  const tracks = useMemo(() => {
    if (!twin) return new Map<string, { name: string; team: string; pts: Track[] }>()
    const map = new Map<string, { name: string; team: string; pts: Track[] }>()
    for (const it of twin) {
      if (!it.player_id || it.x == null || it.y == null) continue
      let tr = map.get(it.player_id)
      if (!tr) {
        tr = { name: it.player ?? it.player_id, team: it.team, pts: [] }
        map.set(it.player_id, tr)
      }
      tr.pts.push({ t: it.t, x: px(it.x, it.team), y: py(it.y, it.team) })
      if (it.x2 != null && it.y2 != null && it.type === 'Carry') {
        tr.pts.push({ t: it.t + Math.max(it.dur ?? 0, 0.25),
                      x: px(it.x2, it.team), y: py(it.y2, it.team) })
      }
    }
    for (const tr of map.values()) tr.pts.sort((a, b) => a.t - b.t)
    return map
  }, [twin])

  // Ball position at time t (seconds), from the real segments.
  const ballAt = useMemo(() => {
    return (t: number): { x: number; y: number; seg: Seg | null } => {
      if (!segs.length) return { x: 60, y: 40, seg: null }
      const i = lastIndexLE(segs, t)
      if (i < 0) return { x: segs[0].x0, y: segs[0].y0, seg: null }
      const s = segs[i]
      if (t <= s.t1) {
        const f = clamp01((t - s.t0) / (s.t1 - s.t0))
        return { x: lerp(s.x0, s.x1, f), y: lerp(s.y0, s.y1, f), seg: s }
      }
      const next = segs[i + 1]
      if (next) {
        const gap = next.t0 - s.t1
        if (gap > 0 && gap <= 2.5) {
          const f = clamp01((t - s.t1) / gap)
          return { x: lerp(s.x1, next.x0, f), y: lerp(s.y1, next.y0, f), seg: null }
        }
      }
      return { x: s.x1, y: s.y1, seg: null }
    }
  }, [segs])

  const ball = ballAt(T)

  // Trail: the ball's real path over the last ~1.6 s.
  const trail = useMemo(() => {
    if (!segs.length) return []
    const pts: { x: number; y: number }[] = []
    for (let k = 6; k >= 1; k--) {
      const p = ballAt(T - k * 0.26)
      pts.push({ x: p.x, y: p.y })
    }
    return pts
  }, [ballAt, T, segs.length])

  // Player dots: interpolate each player between their own recorded touches.
  const dots = useMemo(() => {
    const out: { id: string; name: string; team: string; x: number; y: number
                 recent: number }[] = []
    for (const [id, tr] of tracks) {
      const i = lastIndexLE(tr.pts, T)
      if (i < 0) continue
      const a = tr.pts[i]
      const age = T - a.t
      const b = tr.pts[i + 1]
      let x = a.x, y = a.y
      if (b && b.t - a.t <= 180) {
        // drift toward the player's next real recorded position (covers
        // goal celebrations and restarts without inventing anything)
        const f = clamp01((T - a.t) / Math.max(0.001, b.t - a.t))
        x = lerp(a.x, b.x, f); y = lerp(a.y, b.y, f)
      } else if (age > 90) {
        continue // no recent knowledge of this player -> honestly absent
      }
      out.push({ id, name: tr.name, team: tr.team, x, y, recent: age })
    }
    return out
  }, [tracks, T])

  const carrier = ball.seg?.player ?? null

  // Sparse fallback (no twin stream): v1 behavior over normalized events.
  const sparse = useMemo(() => {
    if (twin) return null
    const located = events
      .filter((e) => e.x !== null && e.y !== null)
      .map((e) => ({
        minute: e.minute, type: e.type, team: e.team,
        player_id: e.player_id, player: e.player,
        x: px(Math.min(100, e.x as number), e.team) ,
        y: py(Math.min(100, e.y as number), e.team),
      }))
      .sort((a, b) => a.minute - b.minute)
    let prev = located[0]
    let pos = { x: 60, y: 40 }
    if (located.length && clock > located[0].minute) {
      for (const p of located) {
        if (p.minute > clock) {
          const span = p.minute - prev.minute
          const f = span > 0 ? clamp01((clock - prev.minute) / span) : 1
          pos = { x: lerp(prev.x, p.x, f), y: lerp(prev.y, p.y, f) }
          break
        }
        prev = p
        pos = { x: p.x, y: p.y }
      }
    }
    return { located, pos }
  }, [twin, events, clock])

  // Cards + goal flash come from the normalized events in both modes.
  const cardPins = events.filter(
    (e) => (e.type === 'yellow_card' || e.type === 'red_card')
      && e.x !== null && e.minute <= clock && e.minute > clock - 3,
  )
  const goalEvent = events.find(
    (e) => e.type === 'goal' && e.minute <= clock && e.minute > clock - 1.4,
  )

  // Activity zones (analysis) from whatever positional truth we have.
  const zones = useMemo(() => {
    if (mode !== 'analysis') return null
    const win: { team: string; x: number; y: number }[] = []
    if (twin) {
      const i0 = lastIndexLE(twin as { t: number }[], T - 12 * 60)
      const i1 = lastIndexLE(twin as { t: number }[], T)
      for (let i = Math.max(0, i0); i <= i1; i++) {
        const it = twin[i]
        if (it.x == null || it.y == null) continue
        win.push({ team: it.team, x: px(it.x, it.team), y: py(it.y, it.team) })
      }
    }
    const zone = (team: string) => {
      const pts = win.filter((p) => p.team === team)
      if (pts.length < 8) return null
      const mx = pts.reduce((s, p) => s + p.x, 0) / pts.length
      const my = pts.reduce((s, p) => s + p.y, 0) / pts.length
      const sx = Math.sqrt(pts.reduce((s, p) => s + (p.x - mx) ** 2, 0) / pts.length)
      const sy = Math.sqrt(pts.reduce((s, p) => s + (p.y - my) ** 2, 0) / pts.length)
      return { cx: mx, cy: my, rx: Math.min(32, Math.max(8, sx * 1.4)),
               ry: Math.min(24, Math.max(6, sy * 1.4)) }
    }
    return { home: zone('HOME'), away: zone('AWAY') }
  }, [mode, twin, T])

  const beat = useMemo(() => {
    if (!story) return null
    let last: StoryBeat | null = null
    for (const b of story) if (b.minute <= clock) last = b
    return last
  }, [story, clock])

  const mm = Math.floor(clock)
  const ss = Math.floor((clock - mm) * 60)
  const momentumDelta = panel.momentum.home - panel.momentum.away

  // HUD score straight from the goal events <= clock, so the scoreboard flips
  // at the exact second of the goal flash (the per-minute panel lags by design).
  const liveScore = useMemo(() => ({
    home: events.filter((e) => e.type === 'goal' && e.team === 'HOME'
                               && e.minute <= clock).length,
    away: events.filter((e) => e.type === 'goal' && e.team === 'AWAY'
                               && e.minute <= clock).length,
  }), [events, clock])

  const askWhy = () => {
    setWhyBusy(true)
    fetchExplain(matchId, Math.round(clock))
      .then(setWhy)
      .catch(() => setWhy(null))
      .finally(() => setWhyBusy(false))
  }

  const shortName = (n: string) => {
    const parts = n.split(' ')
    return parts.length > 1 ? parts[parts.length - 1] : n
  }

  return (
    <div>
      {/* scoreboard — broadcast chip */}
      <div style={{ display: 'flex', gap: 10, alignItems: 'baseline', marginBottom: 8,
                    flexWrap: 'wrap' }}>
        <span style={{ display: 'inline-flex', gap: 8, alignItems: 'baseline',
                       padding: '4px 12px', borderRadius: 8,
                       background: 'var(--surface-1)',
                       border: '1px solid var(--border)',
                       boxShadow: '0 1px 3px rgba(0,0,0,.12)' }}>
          <strong style={{ color: 'var(--home)' }}>{homeName}</strong>
          <strong style={{ fontSize: 18, fontVariantNumeric: 'tabular-nums' }}>
            {liveScore.home}–{liveScore.away}
          </strong>
          <strong style={{ color: 'var(--away)' }}>{awayName}</strong>
          <span style={{ fontVariantNumeric: 'tabular-nums',
                         color: 'var(--text-secondary)', marginLeft: 4 }}>
            {mm}:{String(ss).padStart(2, '0')}
          </span>
        </span>
        {mode !== 'tv' && (
          <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>
            goal in 10&apos;: {Math.round(panel.predictions.goal_next_10min * 100)}%
            {mode === 'analysis' ? ` · ${panel.regime}` : ''}
            {twin ? '' : ' · sparse mode'}
          </span>
        )}
        <span style={{ flex: 1 }} />
        {(['standard', 'tv', 'analysis', 'tactics'] as Mode[]).map((m) => (
          <button key={m} onClick={() => setMode(m)}
                  style={m === mode ? { borderColor: 'var(--seq-450)' } : undefined}>
            {m === 'tv' ? 'TV' : m}
          </button>
        ))}
        {!playing && mode !== 'tv' && (
          <button onClick={askWhy} disabled={whyBusy}>
            {whyBusy ? '…' : `why? (${mm}')`}
          </button>
        )}
      </div>

      <svg viewBox="-2 -2 124 84" style={{ width: '100%', display: 'block',
           borderRadius: 8, boxShadow: '0 2px 10px rgba(0,0,0,.18)' }}
           role="img" aria-label="2D pitch replay">
        <defs>
          <radialGradient id="turfGlow" cx="50%" cy="50%" r="75%">
            <stop offset="0%" stopColor="#478d58" />
            <stop offset="100%" stopColor="#3a7448" />
          </radialGradient>
          <filter id="dotShadow" x="-50%" y="-50%" width="200%" height="200%">
            <feDropShadow dx="0" dy="0.35" stdDeviation="0.35"
                          floodColor="#000" floodOpacity="0.45" />
          </filter>
        </defs>

        {/* turf + mowing stripes */}
        <rect x="-2" y="-2" width="124" height="84" rx="2" fill="url(#turfGlow)" />
        {Array.from({ length: 6 }, (_, i) => (
          <rect key={i} x={i * 20} y="0" width="10" height="80"
                fill="#ffffff" opacity="0.05" />
        ))}

        {/* markings */}
        <g stroke="#ffffff" strokeOpacity="0.85" strokeWidth="0.35" fill="none">
          <rect x="0" y="0" width="120" height="80" />
          <line x1="60" y1="0" x2="60" y2="80" />
          <circle cx="60" cy="40" r="9.15" />
          <circle cx="60" cy="40" r="0.5" fill="#fff" stroke="none" />
          {[0, 1].map((side) => {
            const sgn = side === 0 ? 1 : -1
            const gx = side === 0 ? 0 : 120
            return (
              <g key={side}>
                <rect x={side === 0 ? 0 : 120 - 18} y={40 - 20.16} width="18" height="40.32" />
                <rect x={side === 0 ? 0 : 120 - 6} y={40 - 9.16} width="6" height="18.32" />
                <circle cx={gx + sgn * 12} cy="40" r="0.5" fill="#fff" stroke="none" />
                <path d={`M ${gx + sgn * 18} ${40 - 7.31} A 9.15 9.15 0 0 ${side === 0 ? 1 : 0} ${gx + sgn * 18} ${40 + 7.31}`} />
                <path d={`M ${gx} ${side === 0 ? 2 : 78} A 2 2 0 0 ${side === 0 ? 1 : 0} ${gx + sgn * 2} ${side === 0 ? 0 : 80}`}
                      transform={side === 0 ? '' : ''} opacity="0.7" />
                <rect x={side === 0 ? -1.4 : 120} y={40 - 3.66} width="1.4" height="7.32"
                      fill="#ffffff" fillOpacity="0.9" stroke="none" />
              </g>
            )
          })}
        </g>

        {/* pressure glow at each end (engine reading) */}
        {mode !== 'tv' && (
          <>
            <rect x="96" y="0" width="24" height="80" fill="var(--home)"
                  opacity={Math.min(0.22, panel.pressure.home * 0.22)} />
            <rect x="0" y="0" width="24" height="80" fill="var(--away)"
                  opacity={Math.min(0.22, panel.pressure.away * 0.22)} />
          </>
        )}

        {/* activity zones (analysis) */}
        {zones?.home && (
          <ellipse cx={zones.home.cx} cy={zones.home.cy} rx={zones.home.rx}
                   ry={zones.home.ry} fill="var(--home)" opacity="0.18"
                   stroke="var(--home)" strokeWidth="0.3" />
        )}
        {zones?.away && (
          <ellipse cx={zones.away.cx} cy={zones.away.cy} rx={zones.away.rx}
                   ry={zones.away.ry} fill="#ffffff" opacity="0.22"
                   stroke="#ffffff" strokeWidth="0.3" />
        )}

        {/* momentum arrow (analysis) */}
        {mode === 'analysis' && Math.abs(momentumDelta) > 0.05 && (
          <g opacity="0.85">
            <line x1={60 - momentumDelta * 22} y1="3.5" x2={60 + momentumDelta * 22} y2="3.5"
                  stroke="#ffffff" strokeWidth="1" />
            <path d={momentumDelta > 0
              ? `M ${60 + momentumDelta * 22} 3.5 l -2.2 -1.3 v 2.6 z`
              : `M ${60 + momentumDelta * 22} 3.5 l 2.2 -1.3 v 2.6 z`}
              fill="#ffffff" />
          </g>
        )}

        {/* ── Tactics layer: the intelligent field ────────────────────── */}
        {mode === 'tactics' && tactics && (() => {
          const hx = px(tactics.teams.HOME.block_x, 'HOME')
          const ax = px(tactics.teams.AWAY.block_x, 'AWAY')
          const tl = tactics.top_lane
          const attackRight = tl.team === 'HOME'
          const yc = py(LANE_Y[tl.lane], tl.team)
          const goalX = attackRight ? 118 : 2
          const startX = attackRight ? 62 : 58
          const arrowY = yc
          const pct = Math.round(tactics.goal_next_10min * 100)
          const laneColor = attackRight ? 'var(--home)' : 'var(--away)'
          return (
            <g>
              {/* engagement lines: how high each team is playing */}
              <line x1={hx} y1="2" x2={hx} y2="78" stroke="var(--home)"
                    strokeWidth="0.5" strokeDasharray="2 1.5" opacity="0.8" />
              <line x1={ax} y1="2" x2={ax} y2="78" stroke="var(--away)"
                    strokeWidth="0.5" strokeDasharray="2 1.5" opacity="0.8" />
              {/* territory bar (top): who is camped where */}
              <rect x="0" y="-1.6" width={120 * tactics.territory_home} height="1.2"
                    fill="var(--home)" opacity="0.85" />
              <rect x={120 * tactics.territory_home} y="-1.6"
                    width={120 * (1 - tactics.territory_home)} height="1.2"
                    fill="var(--away)" opacity="0.85" />
              {/* opportunity corridor: the lane the attacker is favouring,
                  as a glowing channel + arrow toward goal, with the chance */}
              <rect x={attackRight ? startX : goalX} y={arrowY - 8}
                    width={Math.abs(goalX - startX)} height="16" rx="3"
                    fill={laneColor} opacity="0.16" />
              <line x1={startX} y1={arrowY} x2={attackRight ? goalX - 3 : goalX + 3}
                    y2={arrowY} stroke={laneColor} strokeWidth="1.1" opacity="0.9" />
              <path d={attackRight
                ? `M ${goalX - 1} ${arrowY} l -3 -2 v 4 z`
                : `M ${goalX + 1} ${arrowY} l 3 -2 v 4 z`}
                fill={laneColor} opacity="0.95" />
              <text x={(startX + goalX) / 2} y={arrowY - 3} textAnchor="middle"
                    fontSize="4" fontWeight="800" fill="#ffffff"
                    stroke="#173322" strokeWidth="0.4" paintOrder="stroke">
                {pct}% next 10&#39;
              </text>
            </g>
          )
        })()}

        {/* live pass line while the ball is in flight */}
        {ball.seg && ball.seg.type !== 'Carry' && (
          <line x1={ball.seg.x0} y1={ball.seg.y0} x2={ball.x} y2={ball.y}
                stroke="#ffffff" strokeWidth="0.35" strokeDasharray="1.2 0.9"
                opacity="0.8" />
        )}

        {/* ball trail */}
        {trail.length > 1 && (
          <polyline
            points={trail.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ')}
            fill="none" stroke="#ffffff" strokeWidth="0.5" strokeLinecap="round"
            opacity="0.35" />
        )}

        {/* player dots — each glides between its own recorded touches */}
        {dots.map((d) => {
          const isHome = d.team === 'HOME'
          const isCarrier = carrier != null && d.name === carrier
          const faded = Math.max(0.45, 1 - d.recent / 60)
          return (
            <g key={d.id} onClick={() => setSelected({ id: d.id, name: d.name })}
               style={{ cursor: 'pointer' }} opacity={faded} filter="url(#dotShadow)">
              <circle cx={d.x} cy={d.y} r={isCarrier ? 1.7 : 1.35}
                      fill={isHome ? 'var(--home)' : '#f3f4f2'}
                      stroke={isHome ? '#ffffff' : '#20242a'}
                      strokeWidth={isCarrier ? 0.4 : 0.28} />
              {mode !== 'tv' && d.recent < 6 && (
                <text x={d.x} y={d.y - 2.2} textAnchor="middle" fontSize="2.6"
                      fontWeight="700" fill="#ffffff" stroke="#1c3a26"
                      strokeWidth="0.35" paintOrder="stroke">
                  {shortName(d.name)}
                </text>
              )}
            </g>
          )
        })}

        {/* sparse-mode pins (fallback when no twin stream) */}
        {sparse && sparse.located
          .filter((p) => p.minute <= clock && p.minute > clock - 1.2)
          .map((p, i) => (
            <circle key={i} cx={p.x} cy={p.y} r="1"
                    fill={p.team === 'HOME' ? 'var(--home)' : '#f3f4f2'} />
          ))}

        {/* card pins */}
        {cardPins.map((p, i) => (
          <rect key={`card-${i}`}
                x={px(Math.min(100, p.x as number), p.team) - 0.9}
                y={py(Math.min(100, p.y as number), p.team) - 1.3}
                width="1.8" height="2.6" rx="0.3"
                fill={p.type === 'red_card' ? '#d33' : '#e6c229'}
                stroke="#20242a" strokeWidth="0.15" />
        ))}

        {/* the ball */}
        <circle cx={sparse ? sparse.pos.x : ball.x} cy={sparse ? sparse.pos.y : ball.y}
                r="1.1" fill="#ffffff" stroke="#20242a" strokeWidth="0.3"
                filter="url(#dotShadow)" />

        {/* goal flash */}
        {goalEvent && (
          <g opacity={Math.max(0, 1 - (clock - goalEvent.minute) / 1.4)}>
            <rect x="0" y="0" width="120" height="80" fill="#ffffff" opacity="0.12" />
            <text x="60" y="41.5" textAnchor="middle" fontSize="8" fontWeight="800"
                  fill={goalEvent.team === 'HOME' ? 'var(--home)' : '#ffffff'}
                  stroke="#173322" strokeWidth="0.5" paintOrder="stroke">
              GOAL {goalEvent.team === 'HOME' ? homeName : awayName}
            </text>
          </g>
        )}
      </svg>

      {/* commentator ticker */}
      {mode !== 'tv' && beat && (
        <div style={{ marginTop: 8, fontSize: 14 }}>
          <span style={{ fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>
            {beat.minute}&#39;
          </span>{' '}
          <strong>{beat.headline}</strong>{' '}
          <span style={{ color: 'var(--text-secondary)' }}>{beat.detail}</span>
        </div>
      )}
      {mode === 'analysis' && (
        <div style={{ marginTop: 4, fontSize: 13, color: 'var(--text-secondary)' }}>
          {panel.explanation.claim}
        </div>
      )}
      {mode === 'tactics' && tactics && (
        <div style={{ marginTop: 6, fontSize: 13 }}>
          <strong>
            {tactics.top_lane.team === 'HOME' ? homeName : awayName}
          </strong>{' '}
          is working the <strong>{tactics.top_lane.lane}</strong> channel
          ({Math.round(tactics.top_lane.share * 100)}% of its recent attacks) —
          a goal in the next 10&#39; reads{' '}
          <strong>{Math.round(tactics.goal_next_10min * 100)}%</strong>.{' '}
          <span style={{ color: 'var(--text-muted)' }}>
            Dashed lines are each team&#39;s line of engagement (mean recent
            action height); the top bar is territory. All from real event
            positions up to this minute.
          </span>
        </div>
      )}

      {selected && (
        <PlayerCard playerId={selected.id} playerName={selected.name}
                    onClose={() => setSelected(null)} />
      )}

      {why && !playing && (
        <div style={{ marginTop: 8, padding: 10, border: '1px solid var(--border)',
                      borderRadius: 6, fontSize: 13 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <strong>{why.claim}</strong>
            <button onClick={() => setWhy(null)} aria-label="close explanation">×</button>
          </div>
          <ul style={{ margin: '6px 0 0 18px', color: 'var(--text-secondary)' }}>
            {why.because.map((b, i) => <li key={i}>{b}</li>)}
          </ul>
          <div style={{ marginTop: 4, color: 'var(--text-muted)' }}>
            reliability {Math.round(why.reliability * 100)}%
          </div>
        </div>
      )}

      <div style={{ marginTop: 6, fontSize: 11, color: 'var(--text-muted)' }}>
        {twin
          ? `Animating ${twin.length.toLocaleString()} real on-ball actions — every pass, carry and shot with its recorded location and sub-second timing. Player dots interpolate only between their own recorded touches; players without recent data honestly disappear. Nothing on this pitch is invented.`
          : `Sparse mode: ball path reconstructed between ${events.filter((e) => e.x !== null).length} real recorded touchpoints. Nothing on this pitch is invented.`}
      </div>
    </div>
  )
}
