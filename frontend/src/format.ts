// Shared tiny formatters (kept in one place — PlayersView, PlayerCard and
// ScoutView all render the same "percentage or em-dash" cells).

/** 0.84 -> "84%"; null/undefined -> "—" (unknown stays visibly unknown). */
export const pct = (v: number | null | undefined): string =>
  v === null || v === undefined ? '—' : `${Math.round(v * 100)}%`
