# FUT-K SDKs

Thin, dependency-free clients for the FUT-K API (levels 12–13 of the product
roadmap). REST is the source of truth — interactive OpenAPI docs live at
`/docs` on a running backend; these SDKs are ergonomic wrappers.

## Python

```python
from futk import FutK          # sdk/python/futk.py — stdlib only

fk = FutK("http://localhost:8000")

fk.matches(competition="43")            # World Cup 2018 catalog
fk.state("7525", minute=43)             # the intelligent panel (leakage-safe)
fk.state_human("7525", minute=43)       # the plain-language reading
fk.story("7525")                        # the narrated Match Story
fk.ask("7525", "why did Saudi Arabia lose?")
fk.similar("7525")                      # semantic search by game dynamics
fk.explain("7525", minute=43)           # claim -> because -> reliability
fk.search("barcelona")
fk.insights("comebacks", team="Real Madrid")
fk.team_evolution("Barcelona")
fk.benchmarks()                         # the public validated numbers
```

## JavaScript

```js
import { FutK } from './futk.js'        // sdk/js/futk.js — fetch only

const fk = new FutK('http://localhost:8000')
const panel = await fk.state('7525', 43)
const answer = await fk.ask('7525', 'what happened after minute 60?')
const twins = await fk.similar('7525')
```

## REST endpoint map

| Product name | Endpoint |
|---|---|
| match | `GET /matches`, `GET /matches/{id}` |
| replay 2D | `GET /matches/{id}/events` (located events) · `GET /matches/{id}/replay2d` (dense twin stream) |
| cross-check | `GET /matches/{id}/crosscheck` (multi-provider fact verification) |
| prediction | `GET /matches/{id}/state?minute=` |
| narrative | `GET /matches/{id}/story`, `GET /matches/{id}/state/human` |
| explain | `GET /matches/{id}/explain?minute=` |
| what if? | `GET /matches/{id}/whatif?minute=&type=&team=` |
| future sim | `GET /matches/{id}/simulate?minute=&seed=` |
| tactics | `GET /matches/{id}/tactics?minute=` |
| strategy | `GET /matches/{id}/decisions?minute=&team=&seed=` |
| search | `GET /search?q=`, `GET /matches/{id}/similar` |
| ask | `GET /matches/{id}/ask?q=` |
| team | `GET /teams/{team}/evolution` |
| player | `GET /players/profiles` |
| network | `GET /matches/{id}/network?side=` |
| insights | `GET /insights/{preset}` |
| benchmarks | `GET /benchmarks` |
| fusion | `GET /fusion/records?team=&league=&conflicts_only=` |

Both SDKs are AGPL-3.0, © 2026 João Vitor Perazzolo (Johnny Kestler).
