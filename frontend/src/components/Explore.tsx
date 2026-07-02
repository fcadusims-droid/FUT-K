// Explore (product level 6): query football history, not just one game.

import { useEffect, useState } from 'react'

interface Row {
  id: string
  competition: string | null
  match_date: string | null
  home_team: string | null
  away_team: string | null
  final: string
  stat: string
}

interface Props {
  onSelect: (id: string) => void
}

export function Explore({ onSelect }: Props) {
  const [presets, setPresets] = useState<Record<string, string>>({})
  const [query, setQuery] = useState('comebacks')
  const [team, setTeam] = useState('')
  const [rows, setRows] = useState<Row[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    fetch('/api/insights/presets').then((r) => r.json()).then(setPresets).catch(() => {})
  }, [])

  useEffect(() => {
    setLoading(true)
    const q = team ? `?team=${encodeURIComponent(team)}` : ''
    fetch(`/api/insights/${query}${q}`)
      .then((r) => r.json())
      .then(setRows)
      .catch(() => setRows([]))
      .finally(() => setLoading(false))
  }, [query, team])

  return (
    <div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 10 }}>
        {Object.entries(presets).map(([id, label]) => (
          <button key={id} className={query === id ? 'primary' : ''} onClick={() => setQuery(id)}>
            {label.split(' — ')[0]}
          </button>
        ))}
        <input
          placeholder="filter by team…"
          value={team}
          onChange={(e) => setTeam(e.target.value)}
          style={{
            font: 'inherit', padding: '6px 10px', borderRadius: 8,
            border: '1px solid var(--border)', background: 'var(--surface-1)',
            color: 'var(--text-primary)',
          }}
        />
      </div>
      <p className="subtitle" style={{ marginBottom: 12 }}>{presets[query] ?? ''}</p>

      <div className="card" style={{ opacity: loading ? 0.6 : 1 }}>
        <table>
          <thead>
            <tr><th>Date</th><th>Match</th><th>Final</th><th>Why it qualifies</th></tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="clickable" onClick={() => onSelect(r.id)}>
                <td style={{ color: 'var(--text-muted)' }}>{r.match_date ?? '—'}</td>
                <td>{r.home_team} vs {r.away_team}</td>
                <td>{r.final}</td>
                <td style={{ color: 'var(--text-secondary)' }}>{r.stat}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!loading && rows.length === 0 && (
          <p style={{ color: 'var(--text-secondary)', margin: '10px 0 0' }}>No matches found.</p>
        )}
      </div>
    </div>
  )
}
