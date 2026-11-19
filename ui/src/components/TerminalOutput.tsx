import { useEffect, useRef } from 'react'
import { CopyButton, StatusBadge, relTime } from 'pnd-lib-react'
import type { CodeTurn } from '../types'

interface Props {
  turns: CodeTurn[]
}

// Map turn statuses onto the library badge's running|done|error|stopped|idle.
const BADGE_STATUS: Record<CodeTurn['status'], string> = {
  ok: 'done',
  error: 'error',
  empty: 'idle',
}

export function TerminalOutput({ turns }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [turns.length])

  if (turns.length === 0) {
    return (
      <p className="term-out__empty">
        No turns yet — enter code mode for this project to see output here.
      </p>
    )
  }

  return (
    <div className="term-out">
      {turns.map((turn) => (
        <div key={turn.id} className="term-out__turn">
          {/* Header row */}
          <div className="term-out__head">
            <span title={turn.timestamp.toISOString()}>{relTime(turn.timestamp.getTime())}</span>
            <StatusBadge status={BADGE_STATUS[turn.status]} />
            <span>{turn.latencyMs}ms</span>
          </div>

          {/* Task (user voice input) */}
          <p className="term-out__task">
            <span className="term-out__prompt">› </span>
            {turn.task}
          </p>

          {/* Response */}
          {turn.response ? (
            <div className="term-out__response">
              <pre>{turn.response}</pre>
              <div className="term-out__copy">
                <CopyButton text={turn.response} label="copy" />
              </div>
            </div>
          ) : (
            <p className="term-out__none">
              {turn.status === 'error' ? 'Error — no response returned.' : 'Empty response.'}
            </p>
          )}
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  )
}
