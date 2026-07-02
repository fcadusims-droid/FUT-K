// Replay a finished match minute by minute: fetch the full panel timeline once,
// scrub client-side. Play/pause/step controls + click-to-seek on the chart.
// A table view twin keeps every value reachable without hover (a11y rule).

import { useEffect, useMemo, useRef, useState } from 'react'
import { fetchMatchDetail, fetchStory, fetchTimeline } from '../api'
import type { MatchDetail, PanelState, StoryBeat } from '../types'
import { MiniCurves } from './MiniCurves'
import { NetworkView } from './NetworkView'
import { Panel } from './Panel'
import { TimelineChart } from './TimelineChart'

interface Props {
  matchId: string
  onBack: () => void
}

export function ReplayView({ matchId, onBack }: Props) {
  const [detail, setDetail] = useState<MatchDetail | null>(null)
  const [timeline, setTimeline] = useState<PanelState[]>([])
  const [idx, setIdx] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [showTable, setShowTable] = useState(false)
  const [analyst, setAnalyst] = useState(false)
  const [story, setStory] = useState<StoryBeat[] | null>(null)
  const [showStory, setShowStory] = useState(true)
  const [showNetwork, setShowNetwork] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const timer = useRef<number | undefined>(undefined)

  useEffect(() => {
    let alive = true
    Promise.all([fetchMatchDetail(matchId), fetchTimeline(matchId, 1)])
      .then(([d, t]) => {
        if (!alive) return
        setDetail(d)
        setTimeline(t)
        setIdx(0)
        fetchStory(matchId).then((s) => alive && setStory(s)).catch(() => {})
      })
      .catch((e) => alive && setError(String(e)))
    return () => {
      alive = false
    }
  }, [matchId])

  useEffect(() => {
    if (!playing) return
    timer.current = window.setInterval(() => {
      setIdx((i) => {
        if (i + 1 >= timeline.length) {
          setPlaying(false)
          return i
        }
        return i + 1
      })
    }, 400)
    return () => window.clearInterval(timer.current)
  }, [playing, timeline.length])

  const panel = timeline[idx]
  const homeName = detail?.home_team ?? 'HOME'
  const awayName = detail?.away_team ?? 'AWAY'

  const seek = useMemo(
    () => (minute: number) => {
      const i = timeline.findIndex((p) => p.minute >= minute)
      setIdx(i === -1 ? timeline.length - 1 : i)
    },
    [timeline],
  )

  if (error) {
    return (
      <div className="card">
        <button onClick={onBack}>← matches</button>
        <p style={{ color: 'var(--text-secondary)' }}>Failed to load match: {error}</p>
      </div>
    )
  }

  if (!detail || !panel) {
    return (
      <div className="card" style={{ opacity: 0.6 }}>
        Loading replay…
      </div>
    )
  }

  return (
    <div>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 12 }}>
        <button onClick={onBack}>← matches</button>
        <span style={{ color: 'var(--text-muted)' }}>
          {detail.competition === '43' ? 'World Cup 2018' : detail.competition === '16' ? 'Champions League final' : 'La Liga 2015/16'}
          {detail.match_date ? ` · ${detail.match_date}` : ''} · final {detail.home_goals_final}–{detail.away_goals_final}
        </span>
      </div>

      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 4 }}>
          <button onClick={() => setAnalyst((a) => !a)}>
            {analyst ? 'Simple view' : 'Analyst mode'}
          </button>
        </div>
        <Panel panel={panel} homeName={homeName} awayName={awayName} analyst={analyst} />
      </div>

      {story && showStory && (
        <div className="card">
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8 }}>
            Match Story
          </div>
          <div style={{ display: 'grid', gap: 8 }}>
            {story.map((b, i) => (
              <div key={i} style={{ display: 'flex', gap: 12, cursor: 'pointer' }}
                   onClick={() => seek(b.minute)}>
                <span style={{ flex: '0 0 34px', textAlign: 'right', fontWeight: 600,
                               fontVariantNumeric: 'tabular-nums' }}>{b.minute}&#39;</span>
                <span>
                  <strong>{b.headline}</strong>{' '}
                  <span style={{ color: 'var(--text-secondary)' }}>{b.detail}</span>
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="card">
        <TimelineChart
          timeline={timeline}
          detail={detail}
          minute={panel.minute}
          onSeek={seek}
          homeName={homeName}
          awayName={awayName}
        />

        {analyst && <MiniCurves timeline={timeline} homeName={homeName} awayName={awayName} />}

        <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 12 }}>
          <button className="primary" onClick={() => setPlaying((p) => !p)}>
            {playing ? 'Pause' : 'Play'}
          </button>
          <button onClick={() => setIdx((i) => Math.max(0, i - 1))}>−1'</button>
          <button onClick={() => setIdx((i) => Math.min(timeline.length - 1, i + 1))}>+1'</button>
          <input
            type="range"
            min={0}
            max={timeline.length - 1}
            value={idx}
            onChange={(e) => setIdx(Number(e.target.value))}
            style={{ flex: 1, accentColor: 'var(--seq-450)' }}
            aria-label="replay minute"
          />
          <span style={{ width: 40, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
            {Math.round(panel.minute)}'
          </span>
        </div>
      </div>

      <div className="card">
        <button onClick={() => setShowStory((v) => !v)} style={{ marginRight: 8 }}>
          {showStory ? 'Hide story' : 'Match story'}
        </button>
        <button onClick={() => setShowNetwork((v) => !v)} style={{ marginRight: 8 }}>
          {showNetwork ? 'Hide passing network' : 'Passing network'}
        </button>
        <button onClick={() => setShowTable((s) => !s)}>
          {showTable ? 'Hide table view' : 'Table view'}
        </button>
        {showNetwork && (
          <div style={{ marginTop: 12 }}>
            <NetworkView matchId={matchId} homeName={homeName} awayName={awayName} />
          </div>
        )}
        {showTable && (
          <table style={{ marginTop: 10 }}>
            <thead>
              <tr>
                <th>Minute</th>
                <th>Score</th>
                <th>Regime</th>
                <th>Momentum {homeName}</th>
                <th>Goal in 10'</th>
                <th>Confidence</th>
              </tr>
            </thead>
            <tbody>
              {timeline
                .filter((p) => p.minute % 5 === 0)
                .map((p) => (
                  <tr key={p.minute}>
                    <td>{Math.round(p.minute)}'</td>
                    <td>
                      {p.score.home}–{p.score.away}
                    </td>
                    <td>{p.regime}</td>
                    <td>{Math.round(p.momentum.home * 100)}%</td>
                    <td>{Math.round(p.predictions.goal_next_10min * 100)}%</td>
                    <td>{Math.round(p.confidence * 100)}%</td>
                  </tr>
                ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
