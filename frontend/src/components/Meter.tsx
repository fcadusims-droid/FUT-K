// Probability meter: a single ratio against a limit -> meter form (not a chart).
// Fill and track are steps of the SAME sequential ramp (marks-and-anatomy.md).

interface Props {
  label: string
  value: number // 0..1
}

export function Meter({ label, value }: Props) {
  const pct = Math.round(value * 100)
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '3px 0' }}>
      <span style={{ flex: '0 0 170px', color: 'var(--text-secondary)' }}>{label}</span>
      <div
        role="meter"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label}
        style={{
          flex: 1,
          height: 8,
          borderRadius: 4,
          background: 'var(--seq-150)',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            width: `${pct}%`,
            height: '100%',
            borderRadius: 4,
            background: 'var(--seq-450)',
          }}
        />
      </div>
      <strong style={{ flex: '0 0 44px', textAlign: 'right' }}>{pct}%</strong>
    </div>
  )
}
