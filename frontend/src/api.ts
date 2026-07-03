import type {
  CrossCheck,
  ExplainPayload,
  MatchDetail,
  MatchEvent2D,
  MatchSummary,
  PanelState,
  PlayerProfile,
  StoryBeat,
  TwinStream,
  WhatIfPayload,
} from './types'

const BASE = '/api'

async function get<T>(path: string): Promise<T> {
  const resp = await fetch(`${BASE}${path}`)
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

export const fetchTwinStream = (id: string) =>
  get<TwinStream>(`/matches/${id}/replay2d`)

export const fetchCrossCheck = (id: string) =>
  get<CrossCheck>(`/matches/${id}/crosscheck`)
