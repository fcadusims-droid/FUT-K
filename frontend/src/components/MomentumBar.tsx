// Two-team share of recent momentum: a part-to-whole of exactly two segments.
// Team hues are fixed (HOME slot 1, AWAY slot 2 — color follows the entity);
// a 2px surface gap separates the fills; team names are always direct-labeled
// (the relief rule for the aqua slot on light surfaces).

interface Props {
  home: number // 0..1 (away share is the complement)
  homeName: string
  awayName: string
}

export function MomentumBar({ home, homeName, awayName }: Props) {
  const homePct = Math.round(home * 100)
  const awayPct = 100 - homePct
  return (
    <div>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          fontSize: 12,
          color: 'var(--text-secondary)',
          marginBottom: 4,
        }}
      >
        <span>
          <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{homePct}%</span>{' '}
          {homeName}
        </span>
        <span>
          {awayName}{' '}
          <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{awayPct}%</span>
        </span>
      </div>
      <div style={{ display: 'flex', gap: 2, height: 10 }}>
        <div
          style={{
            width: `${home * 100}%`,
            background: 'var(--home)',
            borderRadius: '5px 0 0 5px',
          }}
        />
        <div
          style={{
            flex: 1,
            background: 'var(--away)',
            borderRadius: '0 5px 5px 0',
          }}
        />
      </div>
    </div>
  )
}
