import { useState } from 'react'
import { Benchmarks } from './components/Benchmarks'
import { Explore } from './components/Explore'
import { MatchList } from './components/MatchList'
import { ReplayView } from './components/ReplayView'

type Tab = 'matches' | 'explore' | 'benchmarks'

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
        <ReplayView matchId={matchId} onBack={() => setMatchId(null)} onOpenMatch={setMatchId} />
      ) : (
        <>
          <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
            <button className={tab === 'matches' ? 'primary' : ''} onClick={() => setTab('matches')}>
              Matches
            </button>
            <button className={tab === 'explore' ? 'primary' : ''} onClick={() => setTab('explore')}>
              Explore
            </button>
            <button className={tab === 'benchmarks' ? 'primary' : ''} onClick={() => setTab('benchmarks')}>
              Benchmarks
            </button>
          </div>
          {tab === 'matches' ? <MatchList onSelect={setMatchId} /> : tab === 'explore' ? <Explore onSelect={setMatchId} /> : <Benchmarks />}
        </>
      )}
    </>
  )
}
