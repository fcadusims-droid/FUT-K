import type {
  CrossCheck,
  DecisionReport,
  ExplainPayload,
  MatchDetail,
  MatchEvent2D,
  MatchSummary,
  PanelState,
  PlayerProfile,
  ScoutRankings,
  SimilarResponse,
  SimulationResult,
  LiveState,
  StoryBeat,
  TacticalGeometry,
  VisionState,
  TwinStream,
  WhatIfPayload,
} from './types'

const BASE = '/api'

// One query builder for every call: values are URL-encoded uniformly, so a
// competition or team name containing `&`, `#` or spaces cannot break the URL.
function qs(params: Record<string, string | number | boolean | undefined>): string {
  const q = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') q.set(key, String(value))
  }
  const s = q.toString()
  return s ? `?${s}` : ''
}

const enc = encodeURIComponent

async function get<T>(path: string): Promise<T> {
  const resp = await fetch(`${BASE}${path}`)
  if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText} for ${path}`)
  return resp.json() as Promise<T>
}

async function post<T>(path: string): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, { method: 'POST' })
  if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText} for ${path}`)
  return resp.json() as Promise<T>
}

export const fetchMatches = (competition?: string) =>
  get<MatchSummary[]>(`/matches${qs({ competition })}`)

export const fetchMatchDetail = (id: string) => get<MatchDetail>(`/matches/${enc(id)}`)

export const fetchTimeline = (id: string, step = 1) =>
  get<PanelState[]>(`/matches/${enc(id)}/timeline${qs({ step })}`)

export const fetchStory = (id: string) =>
  get<StoryBeat[]>(`/matches/${enc(id)}/story`)

export const fetchEvents = (id: string) =>
  get<MatchEvent2D[]>(`/matches/${enc(id)}/events`)

export const fetchExplain = (id: string, minute: number) =>
  get<ExplainPayload>(`/matches/${enc(id)}/explain${qs({ minute })}`)

export const fetchWhatIf = (id: string, minute: number, type: string, team: string) =>
  get<WhatIfPayload>(`/matches/${enc(id)}/whatif${qs({ minute, type, team })}`)

export const fetchPlayerProfile = (playerId: string) =>
  get<PlayerProfile[]>(`/players/profiles${qs({ player_id: playerId })}`)

export const fetchSimilarPlayers = (playerId: string, limit = 5) =>
  get<SimilarResponse>(`/players/${enc(playerId)}/similar${qs({ limit })}`)

export interface ScoutFilters {
  position?: string
  maxAge?: number
  minConfidence?: number
  competition?: string
  season?: string
}

export const fetchScoutRankings = (opts: ScoutFilters = {}) =>
  get<ScoutRankings>(`/scout/rankings${qs({
    position: opts.position,
    max_age: opts.maxAge,
    min_confidence: opts.minConfidence,
    competition: opts.competition,
    season: opts.season,
  })}`)

export interface ProfileFilters {
  team?: string
  archetype?: string
  minActions?: number
  minConfidence?: number
}

export const fetchPlayerProfiles = (opts: ProfileFilters = {}) =>
  get<PlayerProfile[]>(`/players/profiles${qs({
    team: opts.team,
    archetype: opts.archetype,
    min_actions: opts.minActions,
    min_confidence: opts.minConfidence,
  })}`)

export const fetchTwinStream = (id: string) =>
  get<TwinStream>(`/matches/${enc(id)}/replay2d`)

export const fetchCrossCheck = (id: string) =>
  get<CrossCheck>(`/matches/${enc(id)}/crosscheck`)

export const fetchTactics = (id: string, minute: number) =>
  get<TacticalGeometry>(`/matches/${enc(id)}/tactics${qs({ minute: minute.toFixed(2) })}`)

export const liveReplayFeed = (id: string, upto: number) =>
  post<LiveState>(`/live/${enc(id)}/replay_feed${qs({ upto: upto.toFixed(2) })}`)

export const fetchVision = (id: string, minute: number, evaluate = false) =>
  get<VisionState>(`/matches/${enc(id)}/vision${qs({
    minute: minute.toFixed(3),
    evaluate: evaluate || undefined,
  })}`)

export const fetchDecisions = (id: string, minute: number, team: string, seed = 0) =>
  get<DecisionReport>(`/matches/${enc(id)}/decisions${qs({
    minute: minute.toFixed(2), team, seed,
  })}`)

export const fetchSimulation = (id: string, minute: number, seed = 0) =>
  get<SimulationResult>(`/matches/${enc(id)}/simulate${qs({
    minute: minute.toFixed(2), seed,
  })}`)
