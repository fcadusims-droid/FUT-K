// Player DNA — a browsable, filterable directory of the profiles the engine
// built from real event data. Every row carries its evidence-based confidence
// and provenance (match count + data sources); nothing here is fabricated.
// Deep-linkable: /players lists, /player/:id opens one profile.

import { useEffect, useState } from 'react'
import { fetchPlayerProfiles } from '../api'
import type { PlayerProfile } from '../types'
import { PlayerCard } from './PlayerCard'

interface Props {
  selectedId: string | null
  onSelect: (id: string | null) => void
}

// The descriptive archetypes the profiling layer can assign (fie/profiling.py).
const ARCHETYPES = ['finisher', 'creator', 'balanced', 'conservative', 'impulsive']

const pct = (v: number | null | undefined) =>
  v === null || v === undefined ? '—' : `${Math.round(v * 100)}%`

export function PlayersView({ selectedId, onSelect }: Props) {
  const [minConfidence, setMinConfidence] = useState(0)
  const [archetype, setArchetype] = useState('')
  const [rows, setRows] = useState<PlayerProfile[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    setLoading(true)
    // min_actions 60 = the archetype-eligibility threshold (fie/profiling.py):
    // below it a profile is "insufficient_data", so it is not worth listing.
    fetchPlayerProfiles({ minActions: 60, minConfidence, archetype: archetype || undefined })
      .then((r) => {
        if (!alive) return
        setRows(r)
        setError(null)
      })
      .catch((e) => alive && setError(String(e)))
      .finally(() => alive && setLoading(false))
    return () => {
      alive = false
    }
  }, [minConfidence, archetype])

  const selectedName = rows.find((r) => r.player_id === selectedId)?.name ?? null

  return (
    <div>
      <div style={{ display: 'flex', gap: 16, marginBottom: 14, flexWrap: 'wrap', alignItems: 'center' }}>
        <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 13 }}>
          Archetype
          <select value={archetype} onChange={(e) => setArchetype(e.target.value)}>
            <option value="">any</option>
            {ARCHETYPES.map((a) => (
              <option key={a} value={a}>{a}</option>
            ))}
          </select>
        </label>
        <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 13 }}>
          Min confidence: <strong>{pct(minConfidence)}</strong>
          <input
            type="range" min={0} max={0.9} step={0.1} value={minConfidence}
            onChange={(e) => setMinConfidence(Number(e.target.value))}
          />
        </label>
      </div>

      {selectedId && (
        <PlayerCard playerId={selectedId} playerName={selectedName}
                    onClose={() => onSelect(null)}
                    onOpenPlayer={(id) => onSelect(id)} />
      )}

      <div className="card" style={{ opacity: loading ? 0.6 : 1, marginTop: selectedId ? 12 : 0 }}>
        {error && <p style={{ color: 'var(--text-secondary)' }}>Failed to load: {error}</p>}
        <table>
          <thead>
            <tr>
              <th>Player</th>
              <th>Team</th>
              <th>Archetype</th>
              <th style={{ textAlign: 'right' }}>Actions</th>
              <th style={{ textAlign: 'right' }}>Goals</th>
              <th style={{ textAlign: 'right' }}>Confidence</th>
              <th>Evidence</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((p) => (
              <tr key={p.player_id} className="clickable" onClick={() => onSelect(p.player_id)}>
                <td>{p.name ?? `player ${p.player_id}`}</td>
                <td style={{ color: 'var(--text-muted)' }}>{p.team ?? '—'}</td>
                <td>{p.archetype ?? '—'}</td>
                <td style={{ textAlign: 'right' }}>{p.actions ?? '—'}</td>
                <td style={{ textAlign: 'right' }}>{p.goals ?? 0}</td>
                <td style={{ textAlign: 'right' }}>{pct(p.confidence)}</td>
                <td style={{ color: 'var(--text-muted)', fontSize: 12 }}>
                  {p.matches ?? '—'} · {p.sources?.length ? p.sources.join(', ') : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!loading && rows.length === 0 && (
          <p style={{ color: 'var(--text-secondary)', margin: '10px 0 0' }}>
            No player profiles match these filters — profiles are built per
            ingested competition by the profile pipeline.
          </p>
        )}
      </div>
    </div>
  )
}
