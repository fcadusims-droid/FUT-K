// Vision Engine panel — the continuous, self-correcting state of the match.
//
// Surfaces what the estimator knows at this minute: how many entities it is
// tracking, how many are directly observed right now vs held (estimated with
// decaying confidence), and — the honest, novel part — its self-evaluation:
// how far its motion model predicted the next real touch, versus assuming the
// player stayed put. On sparse event data the static hold wins, and the panel
// says so plainly.

import { useState } from 'react'
import { fetchVision } from '../api'
import type { VisionState } from '../types'

interface Props {
  matchId: string
  minute: number
}

export function VisionPanel({ matchId, minute }: Props) {
  const [state, setState] = useState<VisionState | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const run = () => {
    setBusy(true)
    setError(null)
    fetchVision(matchId, minute, true)
      .then(setState)
      .catch((e) => setError(String(e)))
      .finally(() => setBusy(false))
  }

  const ents = state ? Object.values(state.entities) : []
  const observed = ents.filter((e) => e.observed).length
  const held = ents.length - observed
  const avgConf = ents.length
    ? ents.reduce((s, e) => s + e.confidence, 0) / ents.length
    : 0
  const ev = state?.self_evaluation

  return (
    <div>
      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8 }}>
        Vision Engine — the continuous estimated state of the match at minute{' '}
        {Math.floor(minute)}&#39;
      </div>
      <button className="primary" onClick={run} disabled={busy}>
        {busy ? 'estimating…' : 'Estimate match state'}
      </button>

      {error && <p style={{ color: 'var(--text-secondary)' }}>Failed: {error}</p>}

      {state && (
        <div style={{ marginTop: 10, display: 'grid', gap: 12 }}>
          <div style={{ display: 'flex', gap: 22, flexWrap: 'wrap' }}>
            <Stat label="entities tracked" value={String(state.n_entities)} />
            <Stat label="observed now" value={String(observed)} accent="var(--home)" />
            <Stat label="held (estimated)" value={String(held)} accent="var(--away)" />
            <Stat label="avg confidence" value={`${Math.round(avgConf * 100)}%`} />
          </div>

          {ev && ev.n > 0 && (
            <div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>
                Self-evaluation — the engine grading its own predictions against
                the next real touch ({ev.n.toLocaleString()} predictions, mean
                gap {ev.mean_gap_seconds}s)
              </div>
              <table>
                <tbody>
                  <tr>
                    <td>Motion-model mean error</td>
                    <td>{ev.mean_error.toFixed(2)} units (~m)</td>
                  </tr>
                  <tr>
                    <td>“Hold last position” baseline</td>
                    <td>{ev.static_baseline_mean.toFixed(2)} units</td>
                  </tr>
                  <tr>
                    <td>Median / p90 error</td>
                    <td>{ev.median_error.toFixed(2)} / {ev.p90_error.toFixed(2)} units</td>
                  </tr>
                </tbody>
              </table>
              <div style={{ marginTop: 6, fontSize: 12, color: 'var(--text-secondary)' }}>
                {ev.beats_static_by > 0
                  ? `The motion model beats holding position by ${ev.beats_static_by.toFixed(2)} units.`
                  : `Honest finding: on sparse event data (touches ~${Math.round(ev.mean_gap_seconds)}s apart), extrapolating a player's velocity does NOT beat holding their last position — so the estimator holds position and decays confidence. The kinematic model is ready for dense tracking feeds, where velocities are real.`}
              </div>
            </div>
          )}

          <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{state.note}</div>
        </div>
      )}
    </div>
  )
}

function Stat({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div>
      <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700, color: accent ?? 'var(--text-primary)' }}>
        {value}
      </div>
    </div>
  )
}
