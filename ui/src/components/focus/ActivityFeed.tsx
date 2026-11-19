import { useDannStore } from '../../hooks/useDannState'
import { TraceBar } from '../VoicePanel'

export function ActivityFeed() {
  const wakePhrase = useDannStore(s => s.persona.wake_phrase)
  const mode        = useDannStore(s => s.mode)
  const project     = useDannStore(s => s.project)
  const pendingStt  = useDannStore(s => s._pendingStt)
  const liveResponse = useDannStore(s => s.liveResponse)
  const voiceTurns  = useDannStore(s => s.voiceTurns)

  const lastTurn = voiceTurns[voiceTurns.length - 1]

  return (
    <div className="activity">
      <div className="activity__meta">
        <span>Mode: <span className="activity__val">{mode}</span></span>
        {project && (
          <>
            <span className="activity__sep">|</span>
            <span>Project: <span className="activity__val">{project}</span></span>
          </>
        )}
      </div>

      {(pendingStt || liveResponse) && (
        <div className="activity__turn">
          {pendingStt && (
            <p className="activity__user">"{pendingStt}"</p>
          )}
          {liveResponse && (
            <p className="activity__reply">
              {liveResponse}
              <span className="activity__caret">▋</span>
            </p>
          )}
        </div>
      )}

      {!pendingStt && !liveResponse && lastTurn && (
        <div className="activity__turn activity__turn--past">
          {lastTurn.userText && <p className="activity__user">"{lastTurn.userText}"</p>}
          {lastTurn.dannText && <p className="activity__reply">{lastTurn.dannText}</p>}
        </div>
      )}

      {lastTurn?.trace && <TraceBar trace={lastTurn.trace} />}

      {!lastTurn && !pendingStt && !liveResponse && (
        <p className="activity__hint">No activity yet — say "{wakePhrase}" to begin.</p>
      )}
    </div>
  )
}
