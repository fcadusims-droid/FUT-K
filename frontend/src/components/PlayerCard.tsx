// Player DNA card: click any event on the pitch and meet the player behind
// it — archetype and the profile metrics built from real event data.

import { useEffect, useState } from 'react'
import { fetchPlayerProfile } from '../api'
import type { PlayerProfile } from '../types'

interface Props {
  playerId: string
  playerName: string | null
  onClose: () => void
}

const pct = (v: number | null | undefined) =>
  v === null || v === undefined ? '—' : `${Math.round(v * 100)}%`

export function PlayerCard({ playerId, playerName, onClose }: Props) {
  const [profile, setProfile] = useState<PlayerProfile | null>(null)
  const [missing, setMissing] = useState(false)

  useEffect(() => {
    let alive = true
    setProfile(null)
    setMissing(false)
    fetchPlayerProfile(playerId)
      .then((rows) => {
        if (!alive) return
        if (rows.length) setProfile(rows[0])
        else setMissing(true)
      })
      .catch(() => alive && setMissing(true))
    return () => {
      alive = false
    }
  }, [playerId])

  return (
    <div style={{ marginTop: 8, padding: 10, border: '1px solid var(--border)',
                  borderRadius: 6, fontSize: 13 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <strong>{profile?.name ?? playerName ?? `player ${playerId}`}</strong>
        <span style={{ display: 'flex', gap: 8, alignItems: 'baseline' }}>
          {profile?.archetype && (
            <span style={{ fontSize: 11, padding: '1px 8px', borderRadius: 999,
                           border: '1px solid var(--baseline)',
                           color: 'var(--text-secondary)' }}>
              {profile.archetype}
            </span>
          )}
          <button onClick={onClose} aria-label="close player card">×</button>
        </span>
      </div>
      {profile ? (
        <table style={{ marginTop: 8 }}>
          <tbody>
            <tr><td>Team · position</td>
                <td>{profile.team ?? '—'} · {profile.position ?? '—'}</td></tr>
            <tr><td>Actions</td><td>{profile.actions ?? '—'}</td></tr>
            <tr><td>Goals · assists</td>
                <td>{profile.goals ?? 0} · {profile.assists ?? 0}</td></tr>
            <tr><td>Pass accuracy</td><td>{pct(profile.pass_accuracy)}</td></tr>
            <tr><td>Key-pass rate</td><td>{pct(profile.key_pass_rate)}</td></tr>
            <tr><td>Shot share</td><td>{pct(profile.shot_share)}</td></tr>
          </tbody>
        </table>
      ) : missing ? (
        <p style={{ color: 'var(--text-secondary)', margin: '8px 0 0' }}>
          No DNA profile for this player yet — profiles are built per ingested
          competition by the profile pipeline.
        </p>
      ) : (
        <p style={{ color: 'var(--text-muted)', margin: '8px 0 0' }}>loading…</p>
      )}
    </div>
  )
}
