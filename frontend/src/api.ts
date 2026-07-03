import type {
  ExplainPayload,
  MatchDetail,
  MatchEvent2D,
  MatchSummary,
  PanelState,
  StoryBeat,
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
