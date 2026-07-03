// The ingested competition catalog, shared by the match list (filter tabs)
// and the replay header (label). WC 2018 and WC 2022 share StatsBomb
// competition id 43 and differ by season, so labels are (competition, season)
// keyed.

export interface CompetitionTab {
  id: string
  season: string // '' = any season of this competition
  label: string
}

export const COMPETITIONS: CompetitionTab[] = [
  { id: '', season: '', label: 'All' },
  { id: '9', season: '281', label: 'Bundesliga 2023/24' },
  { id: '55', season: '282', label: 'Euro 2024' },
  { id: '43', season: '106', label: 'World Cup 2022' },
  { id: '43', season: '3', label: 'World Cup 2018' },
  { id: '16', season: '', label: 'Champions League finals' },
  { id: '11', season: '27', label: 'La Liga 2015/16' },
]

export function competitionLabel(
  competition: string | null,
  season: string | null,
): string {
  const exact = COMPETITIONS.find(
    (c) => c.id === competition && c.season === season,
  )
  if (exact) return exact.label
  const byId = COMPETITIONS.find((c) => c.id === competition && !c.season)
  return byId?.label ?? `competition ${competition ?? '?'}`
}
