# FIE frontend (Phase C)

React + Vite app for the Football Intelligence Engine — the Digital Football
Twin's web surface. Pick a real ingested match and explore it: the living 2D
pitch (Digital Match Twin) animated from real recorded actions over the full
90'+, the Section 22 intelligent panel (score, regime, momentum, predictions
with confidence, the explained "why"), the momentum timeline, **What If?**
counterfactuals, the **Future Simulation** panel, Player DNA on click, and
play/scrub/speed controls. Top-level tabs: Matches, **Players** (the DNA
directory), **Scout** (the discovery radar), Explore, and Benchmarks — every
view deep-linkable via the hash router, with an Auto/Light/Dark theme toggle.

## Run (dev)

Needs the backend running with an ingested database (see `../backend/README.md`):

```bash
# terminal 1 — backend on :8000
cd ../backend
export DATABASE_URL="postgresql+psycopg://fie_app:<pw>@localhost:5432/fie_dev"
uvicorn app.main:app --port 8000

# terminal 2 — frontend on :5173 (proxies /api -> :8000)
npm install
npm run dev
```

## Build

```bash
npm run build   # tsc + vite -> dist/
```

## Design notes

- Visual system follows the dataviz reference palette (CSS custom properties in
  `src/index.css`). Dark mode is user-selectable (`theme.ts` persists the choice
  and sets `data-theme` on `<html>`, which overrides `prefers-color-scheme`;
  the OS preference applies only in Auto). Team identity is fixed and
  high-contrast: HOME = categorical slot 1 (blue), AWAY = slot 8 (orange —
  the colorblind-safe blue↔orange pair, CVD ΔE ~97), ball = white with a dark
  ring; all six palette checks pass in both modes.
- Charts are plain SVG (no chart lib): 2px line, hairline solid gridlines,
  ≥8px goal markers with a 2px surface ring, crosshair + single tooltip, and a
  table-view twin so no value is gated behind hover.
- The replay fetches the full panel timeline once (`/matches/{id}/timeline?step=1`)
  and scrubs client-side.
