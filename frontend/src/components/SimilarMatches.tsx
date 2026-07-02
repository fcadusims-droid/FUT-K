// Semantic search (level 7): matches whose dynamics felt like this one.

import { useEffect, useState } from 'react'

interface Row {
  id: string; similarity: number; home_team: string | null
  away_team: string | null; match_date: string | null; final: string
}

export function SimilarMatches({ matchId, onSelect }: {
  matchId: string; onSelect: (id: string) => void
}) {
  const [rows, setRows] = useState<Row[] | null>(null)

  useEffect(() => {
    setRows(null)
    fetch(`/api/matches/${matchId}/similar?limit=5`)
      .then((r) => r.json())
      .then(setRows)
      .catch(() => setRows([]))
  }, [matchId])

  if (!rows) return <p style={{ color: 'var(--text-muted)' }}>Finding similar matches…</p>
  return (
    <div>
      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 6 }}>
        Matches that felt like this one (by game dynamics: momentum flow, goal
        timing, swings)
      </div>
      <table>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} className="clickable" onClick={() => onSelect(r.id)}>
              <td style={{ color: 'var(--text-muted)' }}>{r.match_date}</td>
              <td>{r.home_team} vs {r.away_team}</td>
              <td>{r.final}</td>
              <td style={{ color: 'var(--text-secondary)' }}>
                {Math.round(r.similarity * 100)}% similar
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
