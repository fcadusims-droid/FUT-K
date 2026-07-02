// The match panel. Default: plain language (product level 3 — no jargon).
// Analyst mode: the full Section 22 technical panel.

import type { PanelState } from '../types'
import { humanize } from '../humanize'
import { Meter } from './Meter'
import { MomentumBar } from './MomentumBar'

interface Props {
  panel: PanelState
  homeName: string
  awayName: string
  analyst: boolean
}

const chip: React.CSSProperties = {
  display: 'inline-block',
  padding: '2px 10px',
  borderRadius: 999,
  border: '1px solid var(--border)',
  color: 'var(--text-secondary)',
  fontSize: 12,
  marginRight: 8,
}

export function Panel({ panel, homeName, awayName, analyst }: Props) {
  const { score, predictions, explanation } = panel
  const human = humanize(panel, homeName, awayName)
  const named = (line: string) =>
    line.replaceAll('HOME', homeName).replaceAll('AWAY', awayName)

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 16, marginBottom: 10 }}>
        <div style={{ fontSize: 48, fontWeight: 650 }}>
          {score.home}&thinsp;–&thinsp;{score.away}
        </div>
        <div style={{ color: 'var(--text-secondary)' }}>
          <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
            <span style={{ color: 'var(--home)' }}>●</span> {homeName} vs{' '}
            <span style={{ color: 'var(--away)' }}>●</span> {awayName}
          </div>
          <div>minute {Math.round(panel.minute)}</div>
        </div>
      </div>

      {!analyst ? (
        <div style={{ marginBottom: 8 }}>
          <p style={{ margin: '0 0 6px', fontSize: 16 }}>
            <strong>{human.control}</strong> {human.situation && `${human.situation}.`}
          </p>
          <p style={{ margin: '0 0 6px', color: 'var(--text-secondary)' }}>
            {human.goalOutlook} {human.nextGoal}
          </p>
          {human.reasons.length > 0 && (
            <p style={{ margin: 0, color: 'var(--text-secondary)' }}>
              Mostly because: {human.reasons.join('; ')}.
            </p>
          )}
          {human.hedged && (
            <p style={{ margin: '6px 0 0', color: 'var(--text-muted)', fontStyle: 'italic' }}>
              The picture is still settling — read this with some caution.
            </p>
          )}
        </div>
      ) : (
        <>
          <div style={{ marginBottom: 14 }}>
            <span style={chip}>regime {panel.regime}</span>
            <span style={chip}>confidence {(panel.confidence * 100).toFixed(0)}%</span>
            <span style={chip}>change score {panel.change_score}/100</span>
          </div>

          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 6 }}>
              Momentum (recent)
            </div>
            <MomentumBar home={panel.momentum.home} homeName={homeName} awayName={awayName} />
          </div>

          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>
              Likely next events
            </div>
            <Meter label="Goal in next 5 min" value={predictions.goal_next_5min} />
            <Meter label="Goal in next 10 min" value={predictions.goal_next_10min} />
            <Meter label="Goal before half" value={predictions.goal_before_half} />
            <Meter label={`Next goal: ${homeName}`} value={predictions.next_goal.home} />
          </div>

          <div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>
              Why — {explanation.claim}
            </div>
            {explanation.because.length === 0 ? (
              <div style={{ color: 'var(--text-secondary)' }}>no strong signals right now</div>
            ) : (
              <ul style={{ margin: 0, paddingLeft: 18, color: 'var(--text-secondary)' }}>
                {explanation.because.map((line) => (
                  <li key={line}>{named(line)}</li>
                ))}
              </ul>
            )}
            {explanation.note && (
              <div style={{ color: 'var(--text-muted)', fontStyle: 'italic', marginTop: 4 }}>
                {explanation.note.trim()}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
