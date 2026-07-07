// Player DNA card: click any event on the pitch and meet the player behind
// it — archetype, the profile metrics built from real event data, verified
// bio facts (Wikidata, with provenance), and the most similar profiles.

import { useEffect, useState } from 'react'
import { fetchPlayerProfile, fetchSimilarPlayers } from '../api'
import type { PlayerProfile, SimilarPlayer } from '../types'

interface Props {
  playerId: string
  playerName: string | null
  onClose: () => void
  onOpenPlayer?: (id: string) => void
}

const pct = (v: number | null | undefined) =>
  v === null || v === undefined ? '—' : `${Math.round(v * 100)}%`

export function PlayerCard({ playerId, playerName, onClose, onOpenPlayer }: Props) {
  const [profile, setProfile] = useState<PlayerProfile | null>(null)
  const [similar, setSimilar] = useState<SimilarPlayer[]>([])
  const [missing, setMissing] = useState(false)

  useEffect(() => {
    let alive = true
    setProfile(null)
    setSimilar([])
    setMissing(false)
    fetchPlayerProfile(playerId)
      .then((rows) => {
        if (!alive) return
        if (rows.length) setProfile(rows[0])
        else setMissing(true)
      })
      .catch(() => alive && setMissing(true))
    fetchSimilarPlayers(playerId, 4)
      .then((r) => alive && setSimilar(r.similar))
      .catch(() => {})   // similarity needs >=60 actions; absent is fine
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
            <tr><td>Confidence</td>
                <td title="Evidence-based reliability: a function of on-ball volume, never certainty">
                  {pct(profile.confidence)}</td></tr>
            <tr><td>Evidence</td>
                <td>{profile.matches ?? '—'} match{profile.matches === 1 ? '' : 'es'}
                    {profile.sources?.length ? ` · ${profile.sources.join(', ')}` : ''}</td></tr>
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

      {similar.length > 0 && (
        <div style={{ marginTop: 10 }}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>
            Similar observed profiles (style, not quality)
          </div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {similar.map((s) => (
              <button
                key={s.player_id}
                onClick={() => onOpenPlayer?.(s.player_id)}
                style={{ fontSize: 12 }}
                title={`${s.team ?? ''} · ${s.archetype ?? ''}`}
              >
                {s.name ?? s.player_id} · {Math.round(s.similarity * 100)}%
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
