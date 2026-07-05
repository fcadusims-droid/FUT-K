// A small header control to pick the theme: Auto (follow OS) → Light → Dark.
// The choice persists (theme.ts); Auto respects the user's system setting.

import { useState } from 'react'
import { getTheme, setTheme, type Theme } from '../theme'

const NEXT: Record<Theme, Theme> = { system: 'light', light: 'dark', dark: 'system' }
const LABEL: Record<Theme, string> = { system: '🖥 Auto', light: '☀ Light', dark: '☾ Dark' }

export function ThemeToggle() {
  const [theme, setThemeState] = useState<Theme>(getTheme)

  const cycle = () => {
    const next = NEXT[theme]
    setTheme(next)
    setThemeState(next)
  }

  return (
    <button
      onClick={cycle}
      title="Theme: click to switch Auto / Light / Dark"
      aria-label={`Theme is ${theme}. Click to change.`}
      style={{ whiteSpace: 'nowrap' }}
    >
      {LABEL[theme]}
    </button>
  )
}
