// What If? — the fourth mode: pick a real goal or card, remove it, and watch
// the engine re-read the rest of the match. Baseline (solid) vs counterfactual
// (dashed) on the same axis; the payload's honesty note is rendered verbatim —
// this is a re-reading, not a prophecy.

import { useMemo, useState } from 'react'
import { fetchWhatIf } from '../api'
import type { MatchEvent2D, WhatIfPayload } from '../types'

interface Props {
  matchId: string
  events: MatchEvent2D[]
  homeName: string
  awayName: string
  onSeek: (minute: number) => void
}

const W = 900
const H = 130
const PAD = { left: 36, right: 12, top: 14, bottom: 18 }

function linePath(minutes: number[], values: number[], maxV: number,
                  x0: number, x1: number) {
  const x = (m: number) => PAD.left
    + ((W - PAD.left - PAD.right) * (m - x0)) / Math.max(1, x1 - x0)
  const y = (v: number) => PAD.top
    + (H - PAD.top - PAD.bottom) * (1 - Math.min(1, v / maxV))
  return minutes
    .map((m, i) => `${i === 0 ? 'M' : 'L'}${x(m).toFixed(1)},${y(values[i]).toFixed(1)}`)
    .join(' ')
}

export function WhatIf({ matchId, events, homeName, awayName, onSeek }: Props) {
  const removable = useMemo(
    () =>
      events
        .filter((e) => ['goal', 'red_card', 'yellow_card'].includes(e.type))
        .sort((a, b) => a.minute - b.minute),
    [events],
  )
  const [pick, setPick] = useState(0)
  const [result, setResult] = useState<WhatIfPayload | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (removable.length === 0) return null
  const chosen = removable[Math.min(pick, removable.length - 1)]
  const teamName = (t: string) => (t === 'HOME' ? homeName : awayName)

  const run = () => {
    setBusy(true)
    setError(null)
    fetchWhatIf(matchId, chosen.minute, chosen.type, chosen.team)
      .then(setResult)
      .catch((e) => setError(String(e)))
      .finally(() => setBusy(false))
  }

  const maxV = result
    ? Math.max(
        0.1,
        ...result.baseline.goal_next_10min,
        ...result.counterfactual.goal_next_10min,
      )
    : 1
  const x0 = result?.minutes[0] ?? 0
  const x1 = result ? result.minutes[result.minutes.length - 1] : 90

  return (
    <div>
      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8 }}>
        What If? — remove a real event and let the engine re-read the match
      </div>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        <select
          value={pick}
          onChange={(e) => { setPick(Number(e.target.value)); setResult(null) }}
          aria-label="event to remove"
        >
          {removable.map((e, i) => (
            <option key={i} value={i}>
              {Math.floor(e.minute)}&#39; {e.type.replace('_', ' ')} — {teamName(e.team)}
            </option>
          ))}
        </select>
        <button className="primary" onClick={run} disabled={busy}>
          {busy ? 'replaying…' : 'What if it never happened?'}
        </button>
        {result && (
          <button onClick={() => onSeek(result.from_minute)}>
            jump replay to {result.from_minute}&#39;
          </button>
        )}
      </div>

      {error && <p style={{ color: 'var(--text-secondary)' }}>What-if failed: {error}</p>}

      {result && (
        <div style={{ marginTop: 10 }}>
          <div style={{ fontSize: 14 }}>{result.reading}</div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', margin: '6px 0 2px' }}>
            Goal in the next 10&#39; — with the event (solid) vs without it (dashed)
          </div>
          <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', display: 'block' }}
               role="img" aria-label="what-if divergence chart">
            <line x1={PAD.left} x2={W - PAD.right} y1={H - PAD.bottom} y2={H - PAD.bottom}
                  stroke="var(--gridline)" strokeWidth={1} />
            <path d={linePath(result.minutes, result.baseline.goal_next_10min, maxV, x0, x1)}
                  fill="none" stroke="var(--seq-450)" strokeWidth={2} strokeLinejoin="round" />
            <path d={linePath(result.minutes, result.counterfactual.goal_next_10min, maxV, x0, x1)}
                  fill="none" stroke="var(--seq-450)" strokeWidth={2} strokeDasharray="6 5"
                  strokeLinejoin="round" opacity={0.75} />
            <text x={W - PAD.right} y={PAD.top} textAnchor="end" fontSize={10}
                  fill="var(--text-muted)">
              solid: as it happened · dashed: without the {result.removed.type.replace('_', ' ')}
            </text>
          </svg>
          <table style={{ marginTop: 8 }}>
            <thead>
              <tr>
                <th>Reading at full time</th>
                <th>Score</th>
                <th>Next goal {homeName}</th>
                <th>Momentum {homeName}</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>as it happened</td>
                <td>{result.baseline.score.at(-1)?.join('–')}</td>
                <td>{Math.round((result.baseline.next_goal_home.at(-1) ?? 0) * 100)}%</td>
                <td>{Math.round((result.baseline.momentum_home.at(-1) ?? 0) * 100)}%</td>
              </tr>
              <tr>
                <td>without the event</td>
                <td>{result.counterfactual.score.at(-1)?.join('–')}</td>
                <td>{Math.round((result.counterfactual.next_goal_home.at(-1) ?? 0) * 100)}%</td>
                <td>{Math.round((result.counterfactual.momentum_home.at(-1) ?? 0) * 100)}%</td>
              </tr>
            </tbody>
          </table>
          <div style={{ marginTop: 6, fontSize: 11, color: 'var(--text-muted)' }}>
            {result.note}
          </div>
        </div>
      )}
    </div>
  )
}
