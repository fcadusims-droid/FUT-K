// Theme selection. 'system' follows the OS preference; 'light' / 'dark' are
// explicit user choices, persisted in localStorage and applied via the
// `data-theme` attribute on <html> (whose CSS overrides win over the
// prefers-color-scheme media query — see index.css). An inline script in
// index.html applies the saved choice before first paint to avoid a flash.

export type Theme = 'system' | 'light' | 'dark'

const KEY = 'futk-theme'

export function getTheme(): Theme {
  try {
    const t = localStorage.getItem(KEY)
    if (t === 'light' || t === 'dark') return t
  } catch {
    /* localStorage unavailable — fall back to system */
  }
  return 'system'
}

export function applyTheme(theme: Theme): void {
  const root = document.documentElement
  if (theme === 'system') root.removeAttribute('data-theme')
  else root.setAttribute('data-theme', theme)
}

export function setTheme(theme: Theme): void {
  try {
    if (theme === 'system') localStorage.removeItem(KEY)
    else localStorage.setItem(KEY, theme)
  } catch {
    /* ignore persistence failures — still apply for this session */
  }
  applyTheme(theme)
}
