// The Replay Engine: a continuous match clock drives the living 2D pitch and
// every panel below it. requestAnimationFrame advances the clock (1x = one
// match minute per second, up to 32x); the timeline is fetched once and
// scrubbed client-side. A table view twin keeps every value reachable without
// hover (a11y rule).

import { useEffect, useMemo, useState } from 'react'
import { fetchEvents, fetchMatchDetail, fetchStory, fetchTimeline } from '../api'
import { competitionLabel } from '../competitions'
import type { MatchDetail, MatchEvent2D, PanelState, StoryBeat } from '../types'
import { AskBox } from './AskBox'
import { MiniCurves } from './MiniCurves'
import { PitchReplay } from './PitchReplay'
import { SimilarMatches } from './SimilarMatches'
import { NetworkView } from './NetworkView'
import { Panel } from './Panel'
import { TimelineChart } from './TimelineChart'

interface Props {
  matchId: string
  onBack: () => void
  onOpenMatch: (id: string) => void
}

const SPEEDS = [0.25, 0.5, 1, 2, 8, 32]

export function ReplayView({ matchId, onBack, onOpenMatch }: Props) {
  const [detail, setDetail] = useState<MatchDetail | null>(null)
  const [timeline, setTimeline] = useState<PanelState[]>([])
  const [events2d, setEvents2d] = useState<MatchEvent2D[]>([])
  const [clock, setClock] = useState(1)
  const [speed, setSpeed] = useState(1)
  const [playing, setPlaying] = useState(false)
  const [showTable, setShowTable] = useState(false)
  const [analyst, setAnalyst] = useState(false)
  const [story, setStory] = useState<StoryBeat[] | null>(null)
  const [showStory, setShowStory] = useState(true)
  const [showNetwork, setShowNetwork] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const duration = detail?.duration ?? 90

  useEffect(() => {
    let alive = true
    Promise.all([fetchMatchDetail(matchId), fetchTimeline(matchId, 1)])
      .then(([d, t]) => {
        if (!alive) return
        setDetail(d)
        setTimeline(t)
        setClock(1)
        fetchStory(matchId).then((s) => alive && setStory(s)).catch(() => {})
        fetchEvents(matchId).then((e) => alive && setEvents2d(e)).catch(() => {})
      })
      .catch((e) => alive && setError(String(e)))
    return () => {
      alive = false
    }
  }, [matchId])

  // The match clock: continuous minutes, advanced every animation frame.
  useEffect(() => {
    if (!playing) return
    let raf = 0
    let last = performance.now()
    const tick = (now: number) => {
      const dt = (now - last) / 1000
      last = now
      setClock((c) => {
        const next = c + dt * speed
        if (next >= duration) {
          setPlaying(false)
          return duration
        }
        return next
      })
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [playing, speed, duration])

  // timeline[i] is the panel at minute i+1 (step=1) — derive from the clock.
  const idx = Math.min(timeline.length - 1, Math.max(0, Math.round(clock) - 1))
  const panel = timeline[idx]
  const homeName = detail?.home_team ?? 'HOME'
  const awayName = detail?.away_team ?? 'AWAY'

  const seek = useMemo(
    () => (minute: number) => setClock(Math.max(1, Math.min(minute, duration))),
    [duration],
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
          {competitionLabel(detail.competition, detail.season)}
          {detail.match_date ? ` · ${detail.match_date}` : ''} · final {detail.home_goals_final}–{detail.away_goals_final}
        </span>
      </div>

      <div className="card">
        <PitchReplay
          matchId={matchId}
          events={events2d}
          panel={panel}
          story={story}
          clock={clock}
          playing={playing}
          homeName={homeName}
          awayName={awayName}
        />
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 10 }}>
          <button className="primary" onClick={() => setPlaying((p) => !p)}>
            {playing ? 'Pause' : 'Play'}
          </button>
          <button onClick={() => seek(clock - 1)}>−1&#39;</button>
          <button onClick={() => seek(clock + 1)}>+1&#39;</button>
          <input
            type="range"
            min={1}
            max={duration}
            step={0.1}
            value={clock}
            onChange={(e) => setClock(Number(e.target.value))}
            style={{ flex: 1, accentColor: 'var(--seq-450)' }}
            aria-label="replay clock"
          />
          <span style={{ width: 40, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
            {Math.floor(clock)}&#39;
          </span>
          <span style={{ display: 'inline-flex', gap: 2 }}>
            {SPEEDS.map((s) => (
              <button
                key={s}
                onClick={() => setSpeed(s)}
                style={s === speed ? { borderColor: 'var(--seq-450)', fontWeight: 700 } : undefined}
                aria-label={`speed ${s}x`}
              >
                {s}×
              </button>
            ))}
          </span>
        </div>
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
      </div>

      <div className="card">
        <AskBox matchId={matchId} />
      </div>

      <div className="card">
        <SimilarMatches matchId={matchId} onSelect={onOpenMatch} />
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
