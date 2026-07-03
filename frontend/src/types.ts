// API response shapes (mirrors backend/app/main.py + panel.py).

export interface MatchSummary {
  id: string
  competition: string | null
  season: string | null
  match_date: string | null
  home_team: string | null
  away_team: string | null
  home_goals_final: number | null
  away_goals_final: number | null
}

export interface MatchDetail extends MatchSummary {
  n_events: number
  duration: number
  goal_minutes: { minute: number; team: 'HOME' | 'AWAY' }[]
}

export interface PanelState {
  match_id: string
  minute: number
  score: { home: number; away: number }
  regime: string
  confidence: number
  change_score: number
  momentum: { home: number; away: number }
  pressure: { home: number; away: number }
  predictions: {
    goal_next_5min: number
    goal_next_10min: number
    goal_before_half: number
    next_goal: { home: number; away: number }
  }
  explanation: { claim: string; because: string[]; note: string }
}

export interface StoryBeat {
  minute: number
  headline: string
  detail: string
}

// A normalized event with its real pitch location (engine 0-100 frame, each
// team attacking left -> right). Raw material for the 2D pitch replay.
export interface MatchEvent2D {
  minute: number
  type: string
  team: 'HOME' | 'AWAY'
  x: number | null
  y: number | null
  xg: number | null
}

export interface ExplainPayload {
  claim: string
  probability: number
  because: string[]
  evidence: { metrics_used: number; mechanisms_found: number }
  reliability: number
}
