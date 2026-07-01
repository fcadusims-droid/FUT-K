import { useState } from 'react'
import { MatchList } from './components/MatchList'
import { ReplayView } from './components/ReplayView'

export default function App() {
  const [matchId, setMatchId] = useState<string | null>(null)

  return (
    <>
      <h1>Football Intelligence Engine</h1>
      <p className="subtitle">
        Historical replay — watch the engine read a real match minute by minute:
        state, regime, predictions with confidence, and the why.
      </p>
      {matchId ? (
        <ReplayView matchId={matchId} onBack={() => setMatchId(null)} />
      ) : (
        <MatchList onSelect={setMatchId} />
      )}
    </>
  )
}
