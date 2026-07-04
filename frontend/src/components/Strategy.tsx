// Strategic Assistant — which in-match decision raises the win chance most.
//
// Combines What If? (change the game) with the Future Simulation Engine
// (project the rest) : for the chosen team at this minute it re-simulates the
// remaining match under each candidate approach and ranks them by the change
// in win probability. Honest: a model-based decision aid, not a guarantee.

import { useState } from 'react'
import { fetchDecisions } from '../api'
import type { DecisionReport } from '../types'

interface Props {
  matchId: string
  minute: number
  homeName: string
  awayName: string
}

export function Strategy({ matchId, minute, homeName, awayName }: Props) {
  const [team, setTeam] = useState<'HOME' | 'AWAY'>('HOME')
  const [report, setReport] = useState<DecisionReport | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const run = (t: 'HOME' | 'AWAY') => {
    setTeam(t)
    setBusy(true)
    setError(null)
    fetchDecisions(matchId, minute, t, 0)
      .then(setReport)
      .catch((e) => setError(String(e)))
      .finally(() => setBusy(false))
  }

  const teamName = (t: string) => (t === 'HOME' ? homeName : awayName)
  const maxWin = report ? Math.max(0.01, ...report.decisions.map((d) => d.win)) : 1

  return (
    <div>
      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8 }}>
        Strategic Assistant — which decision raises the win chance most, from
        minute {Math.floor(minute)}&#39;
      </div>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        <button className="primary" onClick={() => run('HOME')} disabled={busy}>
          {busy && team === 'HOME' ? 'weighing options…' : `Advise ${homeName}`}
        </button>
        <button onClick={() => run('AWAY')} disabled={busy}>
          {busy && team === 'AWAY' ? 'weighing options…' : `Advise ${awayName}`}
        </button>
        {report && (
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            {report.n_sims.toLocaleString()} sims/option · horizon{' '}
            {report.horizon_minutes.toFixed(1)} min · seed {report.seed}
          </span>
        )}
      </div>

      {error && <p style={{ color: 'var(--text-secondary)' }}>Failed: {error}</p>}

      {report && (
        <div style={{ marginTop: 10 }}>
          <div style={{ fontSize: 14, marginBottom: 8 }}>
            For <strong>{teamName(report.team)}</strong>, the engine recommends:{' '}
            <strong>
              {report.decisions.find((d) => d.key === report.recommended)?.label
                ?? 'Keep the current shape'}
            </strong>
            {report.recommended !== 'keep' && (() => {
              const rec = report.decisions.find((d) => d.key === report.recommended)
              return rec ? (
                <span style={{ color: 'var(--delta-good)' }}>
                  {' '}(+{Math.round(rec.delta_win * 100)}% win chance)
                </span>
              ) : null
            })()}
          </div>
          <div style={{ display: 'grid', gap: 4 }}>
            {report.decisions.map((d) => (
              <div key={d.key} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ width: 150 }}>
                  {d.label}
                  {d.key === report.recommended && ' ★'}
                </span>
                <span style={{ flex: 1, background: 'var(--gridline)', borderRadius: 3,
                               height: 16, position: 'relative' }}>
                  <span style={{ position: 'absolute', left: 0, top: 0, bottom: 0,
                                 width: `${(d.win / maxWin) * 100}%`,
                                 background: d.key === report.recommended
                                   ? 'var(--delta-good)' : 'var(--seq-450)',
                                 borderRadius: 3 }} />
                </span>
                <span style={{ width: 96, textAlign: 'right',
                               fontVariantNumeric: 'tabular-nums' }}>
                  {Math.round(d.win * 100)}% win
                </span>
                <span style={{ width: 52, textAlign: 'right',
                               fontVariantNumeric: 'tabular-nums',
                               color: d.delta_win > 0 ? 'var(--delta-good)'
                                 : d.delta_win < 0 ? 'var(--away)' : 'var(--text-muted)' }}>
                  {d.delta_win > 0 ? '+' : ''}{Math.round(d.delta_win * 100)}%
                </span>
              </div>
            ))}
          </div>
          <div style={{ marginTop: 6, fontSize: 11, color: 'var(--text-muted)' }}>
            {report.note}
          </div>
        </div>
      )}
    </div>
  )
}
