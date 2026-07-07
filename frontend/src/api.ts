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
  get<MatchSummary[]>(`/matches${competition ? `?competition=${competition}` : ''}`)

export const fetchMatchDetail = (id: string) => get<MatchDetail>(`/matches/${id}`)

export const fetchTimeline = (id: string, step = 1) =>
  get<PanelState[]>(`/matches/${id}/timeline?step=${step}`)

export const fetchStory = (id: string) =>
  get<StoryBeat[]>(`/matches/${id}/story`)

export const fetchEvents = (id: string) =>
  get<MatchEvent2D[]>(`/matches/${id}/events`)

export const fetchExplain = (id: string, minute: number) =>
  get<ExplainPayload>(`/matches/${id}/explain?minute=${minute}`)

export const fetchWhatIf = (id: string, minute: number, type: string, team: string) =>
  get<WhatIfPayload>(
    `/matches/${id}/whatif?minute=${minute}&type=${type}&team=${team}`,
  )

export const fetchPlayerProfile = (playerId: string) =>
  get<PlayerProfile[]>(`/players/profiles?player_id=${playerId}`)

export const fetchSimilarPlayers = (playerId: string, limit = 5) =>
  get<SimilarResponse>(`/players/${playerId}/similar?limit=${limit}`)

export interface ScoutFilters {
  position?: string
  maxAge?: number
  minConfidence?: number
  competition?: string
  season?: string
}

export const fetchScoutRankings = (opts: ScoutFilters = {}) => {
  const q = new URLSearchParams()
  if (opts.position) q.set('position', opts.position)
  if (opts.maxAge) q.set('max_age', String(opts.maxAge))
  if (opts.minConfidence) q.set('min_confidence', String(opts.minConfidence))
  if (opts.competition) q.set('competition', opts.competition)
  if (opts.season) q.set('season', opts.season)
  const qs = q.toString()
  return get<ScoutRankings>(`/scout/rankings${qs ? `?${qs}` : ''}`)
}

export interface ProfileFilters {
  team?: string
  archetype?: string
  minActions?: number
  minConfidence?: number
}

export const fetchPlayerProfiles = (opts: ProfileFilters = {}) => {
  const q = new URLSearchParams()
  if (opts.team) q.set('team', opts.team)
  if (opts.archetype) q.set('archetype', opts.archetype)
  if (opts.minActions) q.set('min_actions', String(opts.minActions))
  if (opts.minConfidence) q.set('min_confidence', String(opts.minConfidence))
  const qs = q.toString()
  return get<PlayerProfile[]>(`/players/profiles${qs ? `?${qs}` : ''}`)
}

export const fetchTwinStream = (id: string) =>
  get<TwinStream>(`/matches/${id}/replay2d`)

export const fetchCrossCheck = (id: string) =>
  get<CrossCheck>(`/matches/${id}/crosscheck`)

export const fetchTactics = (id: string, minute: number) =>
  get<TacticalGeometry>(`/matches/${id}/tactics?minute=${minute.toFixed(2)}`)

export const liveReplayFeed = (id: string, upto: number) =>
  post<LiveState>(`/live/${id}/replay_feed?upto=${upto.toFixed(2)}`)

export const fetchVision = (id: string, minute: number, evaluate = false) =>
  get<VisionState>(
    `/matches/${id}/vision?minute=${minute.toFixed(3)}${evaluate ? '&evaluate=true' : ''}`,
  )

export const fetchDecisions = (id: string, minute: number, team: string, seed = 0) =>
  get<DecisionReport>(
    `/matches/${id}/decisions?minute=${minute.toFixed(2)}&team=${team}&seed=${seed}`,
  )

export const fetchSimulation = (id: string, minute: number, seed = 0) =>
  get<SimulationResult>(
    `/matches/${id}/simulate?minute=${minute.toFixed(2)}&seed=${seed}`,
  )
