import { useEffect } from 'react'
import { Button } from 'pnd-lib-react'
import { useDannStore } from '../../hooks/useDannState'
import LogPanel from '../LogPanel'
import { StateOrb } from '../voice/StateOrb'
import { ActivityFeed } from './ActivityFeed'
import { DevTeamJobs } from './DevTeamJobs'

export function FocusMode({ active, onExit }: { active: boolean; onExit: () => void }) {
  const pipelineStage = useDannStore(s => s.pipelineStage)
  const voiceListening = useDannStore(s => s.voiceListening)
  const running = useDannStore(s => s.running)

  useEffect(() => {
    if (!active) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onExit() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [active, onExit])

  if (!active) return null

  return (
    <div className="focus-mode">
      <div className="focus-mode__bar">
        <span className="focus-mode__title">Focus Mode</span>
        <Button variant="link" onClick={onExit}>Esc to exit</Button>
      </div>

      <div className="focus-mode__body">
        <StateOrb stage={pipelineStage} active={running && voiceListening} size={320} />
        <ActivityFeed />
        <DevTeamJobs />
      </div>

      <div className="focus-mode__log">
        <LogPanel />
      </div>
    </div>
  )
}
