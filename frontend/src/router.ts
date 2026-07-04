// Minimal dependency-free hash router. Deep-linkable URLs (#/match/123,
// #/players, #/player/456) with zero new dependencies — the app stays a single
// self-contained bundle. The hash is the single source of truth for the view.

import { useEffect, useState } from 'react'

const DEFAULT_ROUTE = '/matches'

function currentHash(): string {
  return window.location.hash.slice(1) || DEFAULT_ROUTE
}

/** Subscribe to the current hash route (e.g. "/match/123"). */
export function useHashRoute(): string {
  const [route, setRoute] = useState(currentHash)
  useEffect(() => {
    const onChange = () => setRoute(currentHash())
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  return route
}

/** Navigate to a route; updates the URL hash and triggers a re-render. */
export function navigate(path: string): void {
  window.location.hash = path
}

/** Split "/match/123" into ["match", "123"]; "" / "/" -> []. */
export function routeParts(route: string): string[] {
  return route.split('/').filter(Boolean)
}
