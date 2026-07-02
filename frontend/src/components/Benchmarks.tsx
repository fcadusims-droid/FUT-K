// Public benchmark (level 11): the validated numbers, with reproduction
// commands — continuous proof, straight from the validation pipeline.

import { useEffect, useState } from 'react'

interface Row {
  dataset: string; matches: number; target: string
  brier: number | null; log_loss: number | null; calibration_gap: number | null
  note: string; source: string; reproduce: string
}

export function Benchmarks() {
  const [rows, setRows] = useState<Row[]>([])
  useEffect(() => {
    fetch('/api/benchmarks').then((r) => r.json()).then(setRows).catch(() => {})
  }, [])

  return (
    <div>
      <p className="subtitle" style={{ marginBottom: 12 }}>
        Every number below is produced by a leakage-safe, walk-forward pipeline
        and is reproducible with one command. Details and methodology live in
        the repository's validation folder.
      </p>
      <div className="card">
        <table>
          <thead>
            <tr>
              <th>Dataset</th><th>Matches</th><th>Target</th>
              <th>Brier</th><th>Log loss</th><th>Calibration gap</th><th>Note</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.dataset + r.target}>
                <td>{r.dataset}</td>
                <td>{r.matches}</td>
                <td style={{ color: 'var(--text-secondary)' }}>{r.target}</td>
                <td>{r.brier ?? '—'}</td>
                <td>{r.log_loss ?? '—'}</td>
                <td>{r.calibration_gap ?? '—'}</td>
                <td style={{ color: 'var(--text-secondary)' }}>{r.note}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="card">
        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 6 }}>
          Reproduce any row
        </div>
        {rows.map((r) => (
          <div key={r.dataset + r.target} style={{ marginBottom: 4 }}>
            <code style={{ fontSize: 12 }}>{r.reproduce}</code>
            <span style={{ color: 'var(--text-muted)', fontSize: 12 }}> → {r.source}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
