// Conversational layer (level 8): ask the engine about this match.
// Deterministic Q&A — the engine answers only what it actually knows.

import { useState } from 'react'

export function AskBox({ matchId }: { matchId: string }) {
  const [q, setQ] = useState('')
  const [log, setLog] = useState<{ q: string; a: string }[]>([])
  const [busy, setBusy] = useState(false)

  const send = () => {
    const question = q.trim()
    if (!question || busy) return
    setBusy(true)
    fetch(`/api/matches/${matchId}/ask?q=${encodeURIComponent(question)}`)
      .then((r) => r.json())
      .then((res) => setLog((l) => [...l, { q: question, a: res.answer }]))
      .catch(() => setLog((l) => [...l, { q: question, a: 'Something went wrong.' }]))
      .finally(() => { setBusy(false); setQ('') })
  }

  return (
    <div>
      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 6 }}>
        Ask the engine — e.g. “what happened after minute 60?”, “why did they
        lose?”, “did the referee change the game?”
      </div>
      {log.map((m, i) => (
        <div key={i} style={{ marginBottom: 8 }}>
          <div style={{ fontWeight: 600 }}>{m.q}</div>
          <div style={{ color: 'var(--text-secondary)' }}>{m.a}</div>
        </div>
      ))}
      <div style={{ display: 'flex', gap: 8 }}>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && send()}
          placeholder="Ask about this match…"
          style={{
            flex: 1, font: 'inherit', padding: '7px 10px', borderRadius: 8,
            border: '1px solid var(--border)', background: 'var(--surface-1)',
            color: 'var(--text-primary)',
          }}
        />
        <button className="primary" onClick={send} disabled={busy}>Ask</button>
      </div>
    </div>
  )
}
