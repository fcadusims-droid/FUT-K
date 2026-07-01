// Match catalog: competition filter row above the table (filters scope
// everything below them), rows click through to the replay.

import { useEffect, useState } from 'react'
import { fetchMatches } from '../api'
import type { MatchSummary } from '../types'

interface Props {
  onSelect: (id: string) => void
}

const COMPETITIONS: { id: string; label: string }[] = [
  { id: '', label: 'All' },
  { id: '43', label: 'World Cup 2018' },
  { id: '16', label: 'Champions League finals' },
  { id: '11', label: 'La Liga 2015/16' },
]

export function MatchList({ onSelect }: Props) {
  const [competition, setCompetition] = useState('43')
  const [matches, setMatches] = useState<MatchSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    setLoading(true)
    fetchMatches(competition || undefined)
      .then((m) => {
        if (!alive) return
        setMatches(m)
        setError(null)
      })
      .catch((e) => alive && setError(String(e)))
      .finally(() => alive && setLoading(false))
    return () => {
      alive = false
    }
  }, [competition])

  return (
    <div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 14 }}>
        {COMPETITIONS.map((c) => (
          <button
            key={c.id}
            className={competition === c.id ? 'primary' : ''}
            onClick={() => setCompetition(c.id)}
          >
            {c.label}
          </button>
        ))}
      </div>

      <div className="card" style={{ opacity: loading ? 0.6 : 1 }}>
        {error && <p style={{ color: 'var(--text-secondary)' }}>Failed to load: {error}</p>}
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Match</th>
              <th>Final</th>
            </tr>
          </thead>
          <tbody>
            {matches.map((m) => (
              <tr key={m.id} className="clickable" onClick={() => onSelect(m.id)}>
                <td style={{ color: 'var(--text-muted)' }}>{m.match_date ?? '—'}</td>
                <td>
                  {m.home_team} vs {m.away_team}
                </td>
                <td>
                  {m.home_goals_final}–{m.away_goals_final}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!loading && matches.length === 0 && (
          <p style={{ color: 'var(--text-secondary)', margin: '10px 0 0' }}>
            No matches ingested yet — run the backend ingestion pipeline.
          </p>
        )}
      </div>
    </div>
  )
}
