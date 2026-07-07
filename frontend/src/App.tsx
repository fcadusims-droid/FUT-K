import { Benchmarks } from './components/Benchmarks'
import { Explore } from './components/Explore'
import { MatchList } from './components/MatchList'
import { PlayersView } from './components/PlayersView'
import { ReplayView } from './components/ReplayView'
import { ScoutView } from './components/ScoutView'
import { ThemeToggle } from './components/ThemeToggle'
import { navigate, routeParts, useHashRoute } from './router'

const TABS: { section: string; label: string }[] = [
  { section: 'matches', label: 'Matches' },
  { section: 'players', label: 'Players' },
  { section: 'scout', label: 'Scout' },
  { section: 'explore', label: 'Explore' },
  { section: 'benchmarks', label: 'Benchmarks' },
]

export default function App() {
  const route = useHashRoute()
  const [section = 'matches', param = null] = routeParts(route)

  return (
    <>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
        <h1 style={{ cursor: 'pointer', margin: 0 }} onClick={() => navigate('/matches')}>FUT-K</h1>
        <ThemeToggle />
      </div>
      <p className="subtitle">
        The match intelligence terminal — open any match and understand it like
        a professional analyst.
      </p>
      {section === 'match' && param ? (
        <ReplayView
          matchId={param}
          onBack={() => navigate('/matches')}
          onOpenMatch={(id) => navigate(`/match/${id}`)}
        />
      ) : (
        <>
          <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
            {TABS.map((t) => {
              const active = section === t.section || (t.section === 'players' && section === 'player')
              return (
                <button
                  key={t.section}
                  className={active ? 'primary' : ''}
                  onClick={() => navigate(`/${t.section}`)}
                >
                  {t.label}
                </button>
              )
            })}
          </div>
          {section === 'explore' ? (
            <Explore onSelect={(id) => navigate(`/match/${id}`)} />
          ) : section === 'benchmarks' ? (
            <Benchmarks />
          ) : section === 'scout' ? (
            <ScoutView onSelect={(id) => navigate(`/player/${id}`)} />
          ) : section === 'players' || section === 'player' ? (
            <PlayersView
              selectedId={section === 'player' ? param : null}
              onSelect={(id) => navigate(id ? `/player/${id}` : '/players')}
            />
          ) : (
            <MatchList onSelect={(id) => navigate(`/match/${id}`)} />
          )}
        </>
      )}
    </>
  )
}
