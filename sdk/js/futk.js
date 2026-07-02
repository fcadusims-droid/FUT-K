/**
 * FUT-K JavaScript SDK — a thin fetch client for the FUT-K API.
 * Works in Node 18+ and browsers.
 *
 *   import { FutK } from './futk.js'
 *   const fk = new FutK('http://localhost:8000')
 *   const panel = await fk.state('7525', 43)
 *   const chat = await fk.ask('7525', 'why did Saudi Arabia lose?')
 *
 * Copyright (c) 2026 João Vitor Perazzolo (Johnny Kestler). AGPL-3.0.
 */

export class FutK {
  constructor(baseUrl = 'http://localhost:8000') {
    this.baseUrl = baseUrl.replace(/\/$/, '')
  }

  async _get(path, params = {}) {
    const query = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== undefined && v !== null),
    ).toString()
    const resp = await fetch(`${this.baseUrl}${path}${query ? `?${query}` : ''}`)
    if (!resp.ok) throw new Error(`FUT-K API ${resp.status} for ${path}`)
    return resp.json()
  }

  matches(competition) { return this._get('/matches', { competition }) }
  match(id) { return this._get(`/matches/${id}`) }
  state(id, minute) { return this._get(`/matches/${id}/state`, { minute }) }
  stateHuman(id, minute) { return this._get(`/matches/${id}/state/human`, { minute }) }
  timeline(id, step = 5) { return this._get(`/matches/${id}/timeline`, { step }) }
  story(id) { return this._get(`/matches/${id}/story`) }
  network(id, side = 'HOME') { return this._get(`/matches/${id}/network`, { side }) }
  similar(id, limit = 5) { return this._get(`/matches/${id}/similar`, { limit }) }
  ask(id, question) { return this._get(`/matches/${id}/ask`, { q: question }) }
  explain(id, minute) { return this._get(`/matches/${id}/explain`, { minute }) }
  search(q) { return this._get('/search', { q }) }
  insights(preset, team) { return this._get(`/insights/${preset}`, { team }) }
  insightPresets() { return this._get('/insights/presets') }
  teamEvolution(team, competition) { return this._get(`/teams/${team}/evolution`, { competition }) }
  playerProfiles(opts = {}) { return this._get('/players/profiles', opts) }
  benchmarks() { return this._get('/benchmarks') }
}
