// Scout AI — the discovery radar. Ranks the ingested cohort by a transparent
// scouting index (cohort percentiles of observed rates × evidence volume ×
// age factor when a verified birth date exists). Honest by construction: the
// note under the table states exactly what the number is and is not, and
// age-filtered views only include players whose birth date is verified.

import { useEffect, useState } from 'react'
import { fetchScoutRankings } from '../api'
import type { ScoutRankings } from '../types'

interface Props {
  onSelect: (id: string) => void
}

const pct = (v: number | null | undefined) =>
  v === null || v === undefined ? '—' : `${Math.round(v * 100)}%`

export function ScoutView({ onSelect }: Props) {
  const [position, setPosition] = useState('')
  const [maxAge, setMaxAge] = useState<number | ''>('')
  const [minConfidence, setMinConfidence] = useState(0)
  const [data, setData] = useState<ScoutRankings | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    setLoading(true)
    fetchScoutRankings({
      position: position || undefined,
      maxAge: maxAge === '' ? undefined : maxAge,
      minConfidence,
    })
      .then((d) => {
        if (!alive) return
        setData(d)
        setError(null)
      })
      .catch((e) => alive && setError(String(e)))
      .finally(() => alive && setLoading(false))
    return () => {
      alive = false
    }
  }, [position, maxAge, minConfidence])

  return (
    <div>
      <div style={{ display: 'flex', gap: 16, marginBottom: 14, flexWrap: 'wrap', alignItems: 'center' }}>
        <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 13 }}>
          Position
          <input
            type="text" value={position} placeholder="e.g. forward"
            onChange={(e) => setPosition(e.target.value)}
            style={{ width: 110 }}
          />
        </label>
        <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 13 }}>
          Max age
          <input
            type="number" min={15} max={45} value={maxAge}
            placeholder="any"
            onChange={(e) => setMaxAge(e.target.value === '' ? '' : Number(e.target.value))}
            style={{ width: 70 }}
            title="Only players with a verified birth date appear in age-filtered views"
          />
        </label>
        <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 13 }}>
          Min confidence: <strong>{pct(minConfidence)}</strong>
          <input
            type="range" min={0} max={0.9} step={0.1} value={minConfidence}
            onChange={(e) => setMinConfidence(Number(e.target.value))}
          />
        </label>
        {data && (
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            cohort: {data.cohort_size} players · as of {data.as_of}
          </span>
        )}
      </div>

      <div className="card" style={{ opacity: loading ? 0.6 : 1 }}>
        {error && <p style={{ color: 'var(--text-secondary)' }}>Failed to load: {error}</p>}
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Player</th>
              <th>Team</th>
              <th style={{ textAlign: 'right' }}>Age</th>
              <th style={{ textAlign: 'right' }}>Scout index</th>
              <th>Attack</th>
              <th>Creation</th>
              <th>Progression</th>
              <th style={{ textAlign: 'right' }}>Confidence</th>
            </tr>
          </thead>
          <tbody>
            {data?.players.map((p, i) => (
              <tr key={p.player_id} className="clickable" onClick={() => onSelect(p.player_id)}>
                <td style={{ color: 'var(--text-muted)' }}>{i + 1}</td>
                <td>
                  {p.name ?? `player ${p.player_id}`}
                  {p.bio?.citizenship && (
                    <span style={{ color: 'var(--text-muted)', fontSize: 12 }}> · {p.bio.citizenship}</span>
                  )}
                </td>
                <td style={{ color: 'var(--text-muted)' }}>{p.team ?? '—'}</td>
                <td style={{ textAlign: 'right' }}>{p.age ?? '—'}</td>
                <td style={{ textAlign: 'right' }}>
                  <strong>{p.scout.score.toFixed(1)}</strong>
                </td>
                <td>{pct(p.scout.components.attack)}</td>
                <td>{pct(p.scout.components.creation)}</td>
                <td>{pct(p.scout.components.progression)}</td>
                <td style={{ textAlign: 'right' }}>{pct(p.confidence)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!loading && (data?.players.length ?? 0) === 0 && (
          <p style={{ color: 'var(--text-secondary)', margin: '10px 0 0' }}>
            No players match these filters. Age filters only include players with
            a verified birth date — run the bio enrichment
            (<code>backend/scripts/enrich_bios.py</code>) to add real birth dates
            from Wikidata.
          </p>
        )}
      </div>

      {data && (
        <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 6 }}>
          {data.note}
        </p>
      )}
    </div>
  )
}
