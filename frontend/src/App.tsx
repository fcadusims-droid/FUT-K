import { useState } from 'react'
import { Explore } from './components/Explore'
import { MatchList } from './components/MatchList'
import { ReplayView } from './components/ReplayView'

type Tab = 'matches' | 'explore'

export default function App() {
  const [matchId, setMatchId] = useState<string | null>(null)
  const [tab, setTab] = useState<Tab>('matches')

  return (
    <>
      <h1>FUT-K</h1>
      <p className="subtitle">
        The match intelligence terminal — open any match and understand it like
        a professional analyst.
      </p>
      {matchId ? (
        <ReplayView matchId={matchId} onBack={() => setMatchId(null)} />
      ) : (
        <>
          <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
            <button className={tab === 'matches' ? 'primary' : ''} onClick={() => setTab('matches')}>
              Matches
            </button>
            <button className={tab === 'explore' ? 'primary' : ''} onClick={() => setTab('explore')}>
              Explore
            </button>
          </div>
          {tab === 'matches' ? <MatchList onSelect={setMatchId} /> : <Explore onSelect={setMatchId} />}
        </>
      )}
    </>
  )
}
