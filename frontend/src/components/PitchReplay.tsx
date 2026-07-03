// The Replay Engine's living pitch: a 2D map of the match, animated at the
// display's frame rate. Honest by construction — the ball glides between the
// match's REAL recorded touchpoints (shots, goals, corners, cards, fouls with
// StatsBomb coordinates); team zones are computed from those same locations;
// tint and arrows come from the engine's validated reading (pressure,
// momentum). No player positions are invented: what you see is what the data
// and the engine actually know.
//
// Modes: standard (pitch + engine reading) · tv (just the pitch, minimalist
// broadcast) · analysis (adds activity zones, pressure glow, commentary log).

import { useMemo, useState } from 'react'
import { fetchExplain } from '../api'
import { PlayerCard } from './PlayerCard'
import type { ExplainPayload, MatchEvent2D, PanelState, StoryBeat } from '../types'

type Mode = 'standard' | 'tv' | 'analysis'

interface Props {
  matchId: string
  events: MatchEvent2D[]
  panel: PanelState
  story: StoryBeat[] | null
  clock: number
  playing: boolean
  homeName: string
  awayName: string
}

interface Pt {
  minute: number
  x: number
  y: number
  type: string
  team: 'HOME' | 'AWAY'
  player_id: string | null
  player: string | null
}

// Engine coordinates are 0-100 x 0-100 in the acting team's own attacking
// frame (left -> right). Display frame: a real-proportion 120x80 pitch where
// HOME attacks right and AWAY events are mirrored to sit in the stadium frame.
function toPitch(e: MatchEvent2D): { x: number; y: number } {
  const x = Math.min(100, Math.max(0, e.x ?? 50)) * 1.2
  const y = Math.min(100, Math.max(0, e.y ?? 50)) * 0.8
  return e.team === 'AWAY' ? { x: 120 - x, y: 80 - y } : { x, y }
}

const smooth = (t: number) => t * t * (3 - 2 * t) // smoothstep ease

export function PitchReplay({
  matchId, events, panel, story, clock, playing, homeName, awayName,
}: Props) {
  const [mode, setMode] = useState<Mode>('standard')
  const [why, setWhy] = useState<ExplainPayload | null>(null)
  const [whyBusy, setWhyBusy] = useState(false)
  const [selected, setSelected] = useState<{ id: string; name: string | null } | null>(null)

  const located: Pt[] = useMemo(
    () =>
      events
        .filter((e) => e.x !== null && e.y !== null)
        .map((e) => ({ minute: e.minute, type: e.type, team: e.team,
                       player_id: e.player_id, player: e.player, ...toPitch(e) }))
        .sort((a, b) => a.minute - b.minute),
    [events],
  )

  const pickPlayer = (p: Pt) => {
    if (p.player_id) setSelected({ id: p.player_id, name: p.player })
  }

  // Ball position: interpolate between the two real touchpoints around the
  // clock. Between touches the true path is unknown — the glide is a visual
  // reconstruction between known points, never invented data.
  const ball = useMemo(() => {
    if (located.length === 0) return { x: 60, y: 40 }
    if (clock <= located[0].minute) return { x: 60, y: 40 }
    let prev = located[0]
    for (const p of located) {
      if (p.minute > clock) {
        const span = p.minute - prev.minute
        const t = span > 0 ? smooth(Math.min(1, (clock - prev.minute) / span)) : 1
        return { x: prev.x + (p.x - prev.x) * t, y: prev.y + (p.y - prev.y) * t }
      }
      prev = p
    }
    return { x: prev.x, y: prev.y }
  }, [located, clock])

  // Event pings: brief expanding ring where something just happened.
  const pings = located.filter((p) => p.minute <= clock && p.minute > clock - 1.2)
  const goalFlash = located.find(
    (p) => p.type === 'goal' && p.minute <= clock && p.minute > clock - 1.6,
  )
  // Cards stay pinned a little longer so the eye can find them.
  const cardPins = located.filter(
    (p) => (p.type === 'yellow_card' || p.type === 'red_card')
      && p.minute <= clock && p.minute > clock - 3,
  )

  // Activity zones (analysis): where each team's real events concentrated in
  // the trailing 12 minutes — an honest footprint, not a formation guess.
  const zones = useMemo(() => {
    if (mode !== 'analysis') return null
    const win = located.filter((p) => p.minute <= clock && p.minute > clock - 12)
    const zone = (team: 'HOME' | 'AWAY') => {
      const pts = win.filter((p) => p.team === team)
      if (pts.length < 3) return null
      const mx = pts.reduce((s, p) => s + p.x, 0) / pts.length
      const my = pts.reduce((s, p) => s + p.y, 0) / pts.length
      const sx = Math.sqrt(pts.reduce((s, p) => s + (p.x - mx) ** 2, 0) / pts.length)
      const sy = Math.sqrt(pts.reduce((s, p) => s + (p.y - my) ** 2, 0) / pts.length)
      return { cx: mx, cy: my, rx: Math.min(30, Math.max(6, sx * 1.5)), ry: Math.min(22, Math.max(5, sy * 1.5)) }
    }
    return { home: zone('HOME'), away: zone('AWAY') }
  }, [located, clock, mode])

  const beat = useMemo(() => {
    if (!story) return null
    let last: StoryBeat | null = null
    for (const b of story) if (b.minute <= clock) last = b
    return last
  }, [story, clock])

  // The player behind the most recent touchpoint — click-through to Player DNA.
  const lastTouch = useMemo(() => {
    let last: Pt | null = null
    for (const p of located) {
      if (p.minute > clock) break
      if (p.player_id) last = p
    }
    return last
  }, [located, clock])

  const mm = Math.floor(clock)
  const ss = Math.floor((clock - mm) * 60)
  const momentumDelta = panel.momentum.home - panel.momentum.away

  const askWhy = () => {
    setWhyBusy(true)
    fetchExplain(matchId, Math.round(clock))
      .then(setWhy)
      .catch(() => setWhy(null))
      .finally(() => setWhyBusy(false))
  }

  return (
    <div>
      <div style={{ display: 'flex', gap: 8, alignItems: 'baseline', marginBottom: 6 }}>
        <strong style={{ fontSize: 18, fontVariantNumeric: 'tabular-nums' }}>
          <span style={{ color: 'var(--home)' }}>{homeName}</span>
          {' '}{panel.score.home}–{panel.score.away}{' '}
          <span style={{ color: 'var(--away)' }}>{awayName}</span>
        </strong>
        <span style={{ fontVariantNumeric: 'tabular-nums', color: 'var(--text-secondary)' }}>
          {mm}:{String(ss).padStart(2, '0')}
        </span>
        {mode !== 'tv' && (
          <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>
            goal in 10&apos;: {Math.round(panel.predictions.goal_next_10min * 100)}%
            {mode === 'analysis' ? ` · ${panel.regime}` : ''}
          </span>
        )}
        <span style={{ flex: 1 }} />
        {(['standard', 'tv', 'analysis'] as Mode[]).map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            style={m === mode ? { borderColor: 'var(--seq-450)' } : undefined}
          >
            {m === 'tv' ? 'TV' : m}
          </button>
        ))}
        {!playing && mode !== 'tv' && (
          <button onClick={askWhy} disabled={whyBusy}>
            {whyBusy ? '…' : `why? (${mm}')`}
          </button>
        )}
      </div>

      <svg viewBox="0 0 120 80" style={{ width: '100%', display: 'block', borderRadius: 6 }}
           role="img" aria-label="2D pitch replay">
        {/* turf + markings */}
        <rect x="0" y="0" width="120" height="80" fill="var(--surface-1)" />
        <rect x="0.6" y="0.6" width="118.8" height="78.8" fill="none"
              stroke="var(--baseline)" strokeWidth="0.4" />
        <line x1="60" y1="0.6" x2="60" y2="79.4" stroke="var(--gridline)" strokeWidth="0.4" />
        <circle cx="60" cy="40" r="9.15" fill="none" stroke="var(--gridline)" strokeWidth="0.4" />
        {/* penalty boxes + goals */}
        {[0, 1].map((side) => {
          const x = side === 0 ? 0.6 : 119.4
          const dir = side === 0 ? 1 : -1
          return (
            <g key={side} stroke="var(--gridline)" strokeWidth="0.4" fill="none">
              <rect x={side === 0 ? 0.6 : 119.4 - 18} y={40 - 20.16} width="18" height="40.32" />
              <rect x={side === 0 ? 0.6 : 119.4 - 6} y={40 - 9.16} width="6" height="18.32" />
              <circle cx={x + dir * 12} cy="40" r="0.5" fill="var(--gridline)" stroke="none" />
              <rect x={side === 0 ? 0 : 119.4} y={40 - 3.66} width="0.6" height="7.32"
                    fill="var(--baseline)" stroke="none" />
            </g>
          )
        })}

        {/* pressure glow at each end (the engine's reading, not a guess) */}
        {mode !== 'tv' && (
          <>
            <rect x="96" y="0.6" width="23.4" height="78.8" fill="var(--home)"
                  opacity={Math.min(0.28, panel.pressure.home * 0.28)} />
            <rect x="0.6" y="0.6" width="23.4" height="78.8" fill="var(--away)"
                  opacity={Math.min(0.28, panel.pressure.away * 0.28)} />
          </>
        )}

        {/* activity zones from real event locations (analysis) */}
        {zones?.home && (
          <ellipse cx={zones.home.cx} cy={zones.home.cy} rx={zones.home.rx} ry={zones.home.ry}
                   fill="var(--home)" opacity="0.16" stroke="var(--home)" strokeWidth="0.3" />
        )}
        {zones?.away && (
          <ellipse cx={zones.away.cx} cy={zones.away.cy} rx={zones.away.rx} ry={zones.away.ry}
                   fill="var(--away)" opacity="0.16" stroke="var(--away)" strokeWidth="0.3" />
        )}

        {/* momentum arrow (analysis): who is pushing, and how hard */}
        {mode === 'analysis' && Math.abs(momentumDelta) > 0.05 && (
          <g opacity="0.75">
            <line x1={60 - momentumDelta * 22} y1="4" x2={60 + momentumDelta * 22} y2="4"
                  stroke={momentumDelta > 0 ? 'var(--home)' : 'var(--away)'} strokeWidth="1.1" />
            <path
              d={momentumDelta > 0
                ? `M ${60 + momentumDelta * 22} 4 l -2.2 -1.4 v 2.8 z`
                : `M ${60 + momentumDelta * 22} 4 l 2.2 -1.4 v 2.8 z`}
              fill={momentumDelta > 0 ? 'var(--home)' : 'var(--away)'}
            />
          </g>
        )}

        {/* event pings — something real just happened here; click for the player */}
        {pings.map((p, i) => (
          <g key={`${p.minute}-${i}`} onClick={() => pickPlayer(p)}
             style={p.player_id ? { cursor: 'pointer' } : undefined}>
            <circle cx={p.x} cy={p.y} r={1.2 + (clock - p.minute) * 3.4}
                    fill="none" stroke={p.team === 'HOME' ? 'var(--home)' : 'var(--away)'}
                    strokeWidth="0.5" opacity={Math.max(0, 1 - (clock - p.minute) / 1.2)} />
            {p.type !== 'foul' && (
              <circle cx={p.x} cy={p.y} r="0.9"
                      fill={p.team === 'HOME' ? 'var(--home)' : 'var(--away)'} />
            )}
          </g>
        ))}

        {/* card pins */}
        {cardPins.map((p, i) => (
          <rect key={`card-${i}`} x={p.x - 0.9} y={p.y - 1.3} width="1.8" height="2.6" rx="0.3"
                fill={p.type === 'red_card' ? '#d33' : '#e6c229'}
                stroke="var(--text-primary)" strokeWidth="0.15"
                transform={`rotate(8 ${p.x} ${p.y})`}
                onClick={() => pickPlayer(p)}
                style={p.player_id ? { cursor: 'pointer' } : undefined} />
        ))}

        {/* the ball — gliding between real touchpoints */}
        <circle cx={ball.x} cy={ball.y} r="1.5" fill="var(--text-primary)"
                stroke="var(--surface-1)" strokeWidth="0.4" />

        {/* goal flash */}
        {goalFlash && (
          <text x="60" y="42" textAnchor="middle" fontSize="7" fontWeight="800"
                fill={goalFlash.team === 'HOME' ? 'var(--home)' : 'var(--away)'}
                opacity={Math.max(0, 1 - (clock - goalFlash.minute) / 1.6)}>
            GOAL {goalFlash.team === 'HOME' ? homeName : awayName}
          </text>
        )}
      </svg>

      {/* commentator ticker: the engine narrating as the clock passes */}
      {mode !== 'tv' && beat && (
        <div style={{ marginTop: 8, fontSize: 14 }}>
          <span style={{ fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>
            {beat.minute}&#39;
          </span>{' '}
          <strong>{beat.headline}</strong>{' '}
          <span style={{ color: 'var(--text-secondary)' }}>{beat.detail}</span>
        </div>
      )}
      {mode !== 'tv' && lastTouch && (
        <div style={{ marginTop: 4, fontSize: 12, color: 'var(--text-secondary)' }}>
          last touch:{' '}
          <button
            onClick={() => pickPlayer(lastTouch)}
            style={{ fontSize: 12, padding: '0 8px' }}
          >
            {Math.floor(lastTouch.minute)}&#39; {lastTouch.type.replace('_', ' ')} —{' '}
            {lastTouch.player ?? `player ${lastTouch.player_id}`}
          </button>{' '}
          <span style={{ color: 'var(--text-muted)' }}>(click for Player DNA)</span>
        </div>
      )}

      {selected && (
        <PlayerCard
          playerId={selected.id}
          playerName={selected.name}
          onClose={() => setSelected(null)}
        />
      )}
      {mode === 'analysis' && (
        <div style={{ marginTop: 4, fontSize: 13, color: 'var(--text-secondary)' }}>
          {panel.explanation.claim}
        </div>
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
        Ball path reconstructed between {located.length} real recorded touchpoints;
        zones and tints computed from real event locations and the engine&apos;s
        validated reading. Nothing on this pitch is invented.
      </div>
    </div>
  )
}
