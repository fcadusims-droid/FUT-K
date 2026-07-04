// Live Mode — the same engine, fed one observation at a time.
//
// A real deployment streams observations from a feed through the fusion layer;
// this card demonstrates that path by replaying the match's real events one by
// one through the live session (event bus → panel + Vision listeners) up to the
// current minute. Because the engine is leakage-safe, the streamed live state
// is identical to the batch panel — the card shows that verification badge, the
// honest proof the streaming path changed none of the maths.

import { useState } from 'react'
import { liveReplayFeed } from '../api'
import type { LiveState } from '../types'

interface Props {
  matchId: string
  minute: number
  homeName: string
  awayName: string
}

export function LivePanel({ matchId, minute, homeName, awayName }: Props) {
  const [state, setState] = useState<LiveState | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const run = () => {
    setBusy(true)
    setError(null)
    liveReplayFeed(matchId, minute)
      .then(setState)
      .catch((e) => setError(String(e)))
      .finally(() => setBusy(false))
  }

  return (
    <div>
      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8 }}>
        Live Mode — stream the match one observation at a time (event bus →
        panel + Vision), up to minute {Math.floor(minute)}&#39;
      </div>
      <button className="primary" onClick={run} disabled={busy}>
        {busy ? 'streaming…' : 'Stream to this minute'}
      </button>

      {error && <p style={{ color: 'var(--text-secondary)' }}>Failed: {error}</p>}

      {state && (
        <div style={{ marginTop: 10 }}>
          <div style={{ display: 'flex', gap: 10, alignItems: 'baseline', flexWrap: 'wrap' }}>
            <strong style={{ fontSize: 18 }}>
              <span style={{ color: 'var(--home)' }}>{homeName}</span>{' '}
              {state.panel.score.home}–{state.panel.score.away}{' '}
              <span style={{ color: 'var(--away)' }}>{awayName}</span>
            </strong>
            <span style={{ color: 'var(--text-muted)', fontVariantNumeric: 'tabular-nums' }}>
              {Math.floor(state.minute)}&#39; · {state.n_events} events streamed ·
              goal in 10&apos;: {Math.round(state.panel.predictions.goal_next_10min * 100)}%
            </span>
            {state.matches_batch && (
              <span style={{ fontSize: 11, padding: '1px 8px', borderRadius: 999,
                             border: '1px solid var(--baseline)',
                             color: 'var(--delta-good)' }}>
                ✓ streaming reproduces the batch panel exactly
              </span>
            )}
          </div>
          {state.log.length > 0 && (
            <div style={{ marginTop: 6, fontSize: 13, color: 'var(--text-secondary)' }}>
              {state.log.join('  ·  ')}
            </div>
          )}
          <div style={{ marginTop: 6, fontSize: 11, color: 'var(--text-muted)' }}>
            The event bus (deferred in the architecture until live feeds arrived)
            now delivers each observation to the panel and Vision-Engine
            listeners. The ✓ badge is the leakage-safe guarantee: the live path
            and the batch path agree to the byte.
          </div>
        </div>
      )}
    </div>
  )
}
