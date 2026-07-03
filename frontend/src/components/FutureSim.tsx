// Future Simulation Engine — thousands of futures from this minute.
//
// Runs seeded Monte-Carlo forward simulations of the REMAINING match (a
// horizon derived from the match's real recorded duration — never a hardcoded
// 90) and shows the outcome distribution + opportunity windows: the lanes and
// short time slices where the next chance is most likely to form. Honest by
// construction: probabilities, not prophecy; the seed is shown so any run is
// reproducible.

import { useState } from 'react'
import { fetchSimulation } from '../api'
import type { SimulationResult } from '../types'

interface Props {
  matchId: string
  minute: number
  homeName: string
  awayName: string
}

const laneLabel = (l: string) => l
const mmss = (sec: number) => {
  const m = Math.floor(sec / 60)
  const s = Math.round(sec % 60)
  return m > 0 ? `${m}m ${s}s` : `${s}s`
}

export function FutureSim({ matchId, minute, homeName, awayName }: Props) {
  const [result, setResult] = useState<SimulationResult | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const run = () => {
    setBusy(true)
    setError(null)
    fetchSimulation(matchId, minute, 0)
      .then(setResult)
      .catch((e) => setError(String(e)))
      .finally(() => setBusy(false))
  }

  const teamName = (t: string) => (t === 'HOME' ? homeName : awayName)
  const maxScoreProb = result
    ? Math.max(0.01, ...result.scorelines.map((s) => s.prob))
    : 1

  return (
    <div>
      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8 }}>
        Future Simulation — project the rest of the match from minute{' '}
        {Math.floor(minute)}&#39;
      </div>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        <button className="primary" onClick={run} disabled={busy}>
          {busy ? 'simulating 10,000 futures…' : 'Simulate the next minutes'}
        </button>
        {result && (
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            {result.n_sims.toLocaleString()} sims · horizon{' '}
            <strong>{result.horizon_minutes.toFixed(1)} min</strong> of real time
            left (match runs to {result.real_duration.toFixed(1)}&#39;) · seed{' '}
            {result.seed}
          </span>
        )}
      </div>

      {error && <p style={{ color: 'var(--text-secondary)' }}>Simulation failed: {error}</p>}

      {result && result.horizon_minutes <= 0.05 && (
        <p style={{ marginTop: 10, color: 'var(--text-secondary)' }}>
          No real time remaining — the match is essentially over, nothing left
          to simulate.
        </p>
      )}

      {result && result.horizon_minutes > 0.05 && (
        <div style={{ marginTop: 10, display: 'grid', gap: 14 }}>
          <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap' }}>
            {(['home', 'any', 'away'] as const).map((k) => (
              <div key={k}>
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                  {k === 'any' ? 'any goal' : `${teamName(k.toUpperCase())} scores`}
                </div>
                <div style={{ fontSize: 22, fontWeight: 700,
                              color: k === 'home' ? 'var(--home)'
                                : k === 'away' ? 'var(--away)' : 'var(--text-primary)' }}>
                  {Math.round(result.goal_prob[k] * 100)}%
                </div>
              </div>
            ))}
            <div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                expected goals (rest of match)
              </div>
              <div style={{ fontSize: 22, fontWeight: 700 }}>
                {result.expected_goals.home.toFixed(2)}
                <span style={{ color: 'var(--text-muted)' }}> – </span>
                {result.expected_goals.away.toFixed(2)}
              </div>
            </div>
          </div>

          <div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>
              Most likely remaining scorelines (goals from now to full time)
            </div>
            <div style={{ display: 'grid', gap: 3 }}>
              {result.scorelines.map((s) => (
                <div key={s.score} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ width: 44, fontVariantNumeric: 'tabular-nums' }}>
                    +{s.score}
                  </span>
                  <span style={{ flex: 1, background: 'var(--gridline)', borderRadius: 3,
                                 height: 14, position: 'relative' }}>
                    <span style={{ position: 'absolute', left: 0, top: 0, bottom: 0,
                                   width: `${(s.prob / maxScoreProb) * 100}%`,
                                   background: 'var(--seq-450)', borderRadius: 3 }} />
                  </span>
                  <span style={{ width: 40, textAlign: 'right',
                                 fontVariantNumeric: 'tabular-nums' }}>
                    {Math.round(s.prob * 100)}%
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>
              Opportunity windows — where and when the next chance is most likely
            </div>
            {result.opportunity_windows.length === 0 ? (
              <p style={{ color: 'var(--text-secondary)', fontSize: 13 }}>
                No lane stands out — chances are spread evenly across the pitch.
              </p>
            ) : (
              <div style={{ display: 'grid', gap: 4 }}>
                {result.opportunity_windows.slice(0, 4).map((w, i) => (
                  <div key={i} style={{ fontSize: 13, display: 'flex', gap: 8,
                                        alignItems: 'baseline' }}>
                    <span style={{ width: 8, height: 8, borderRadius: 999,
                                   background: w.team === 'HOME' ? 'var(--home)' : 'var(--away)',
                                   display: 'inline-block' }} />
                    <strong>{teamName(w.team)}</strong>
                    <span>down the <strong>{laneLabel(w.lane)}</strong></span>
                    <span style={{ color: 'var(--text-secondary)' }}>
                      — {Math.round(w.probability * 100)}% chance, likely around{' '}
                      {mmss(w.eta_seconds)} from now
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            {result.note}
          </div>
        </div>
      )}
    </div>
  )
}
