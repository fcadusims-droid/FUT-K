// Plain-language reading of a panel state (mirrors backend app/story.py).
// The default view speaks like an analyst friend, never in engine jargon.

import type { PanelState } from './types'

const REGIME_PHRASES: Record<string, string> = {
  NORMAL: 'The game is balanced',
  PRESSURE: '{dom} is piling on the pressure',
  POST_GOAL: 'The match is resettling after the goal',
  POST_RED_CARD: 'The red card has reshaped the game',
  DESPERATION: '{trail} is chasing the game',
  END_GAME: 'The finale — every ball matters',
}

export interface HumanView {
  control: string
  situation: string
  goalOutlook: string
  nextGoal: string
  reasons: string[]
  hedged: boolean
}

export function humanize(panel: PanelState, home: string, away: string): HumanView {
  const mom = panel.momentum.home
  const [dom, domShare] = mom >= 0.5 ? [home, mom] : [away, 1 - mom]
  const trail = panel.score.home > panel.score.away ? away : home

  const control =
    domShare > 0.72
      ? `${dom} is dominating territorially (${Math.round(domShare * 100)}% of recent momentum).`
      : domShare > 0.58
        ? `${dom} has the upper hand right now.`
        : 'Neither side is on top — the game is in the balance.'

  const situation = (REGIME_PHRASES[panel.regime] ?? '')
    .replace('{dom}', dom)
    .replace('{trail}', trail)

  const p10 = panel.predictions.goal_next_10min
  const goalOutlook =
    p10 >= 0.45
      ? `A goal feels close — ${Math.round(p10 * 100)}% chance in the next 10 minutes.`
      : p10 >= 0.25
        ? `A goal in the next 10 minutes is plausible (${Math.round(p10 * 100)}%).`
        : `A quiet spell is more likely — only ${Math.round(p10 * 100)}% chance of a goal soon.`

  const ng = panel.predictions.next_goal
  const [fav, favP] = ng.home >= 0.5 ? [home, ng.home] : [away, ng.away]

  const reasons = panel.explanation.because
    .filter((l) => !l.startsWith('the game shifted'))
    .map((l) => l.replace('✓ ', '').replaceAll('HOME', home).replaceAll('AWAY', away))

  return {
    control,
    situation,
    goalOutlook,
    nextGoal: `If a goal comes, it favors ${fav} (${Math.round(favP * 100)}%).`,
    reasons,
    hedged: panel.explanation.note !== '',
  }
}
