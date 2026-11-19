import { Suspense, lazy, useEffect, useState } from 'react'
import { Card, IconButton, Tabs } from 'pnd-lib-react'
import { useDannStore } from '../hooks/useDannState'
import type { TerminalSession } from '../types'

const TerminalPane = lazy(() => import('./TerminalPane'))

function TerminalIcon() {
  return (
    <svg viewBox="0 0 24 24" className="term-icon" fill="none" stroke="currentColor" strokeWidth={2}>
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M7 9l3 3-3 3M13 15h4" />
    </svg>
  )
}

function label(t: TerminalSession): string {
  return t.project ? `${t.focus_area} · ${t.project}` : t.focus_area ?? t.session_id.slice(0, 8)
}

export function TerminalIndicator() {
  const personaName = useDannStore((s) => s.persona.name)
  const terminals = useDannStore((s) => s.terminals)
  const dannTerminals = terminals.filter((t) => t.origin === 'dann' && t.alive)

  const [open, setOpen] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)

  // Default to the most recently listed one whenever the set changes and
  // nothing (or something now-closed) is selected.
  useEffect(() => {
    if (dannTerminals.length === 0) { setSelectedId(null); return }
    if (!selectedId || !dannTerminals.some((t) => t.session_id === selectedId)) {
      setSelectedId(dannTerminals[dannTerminals.length - 1].session_id)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dannTerminals.map((t) => t.session_id).join(',')])

  if (dannTerminals.length === 0) return null

  const selected = dannTerminals.find((t) => t.session_id === selectedId) ?? dannTerminals[0]

  return (
    <>
      <IconButton
        label={`${personaName} is using Claude Code — click to watch`}
        onClick={() => setOpen(true)}
        className="term-fab"
      >
        <span className="term-fab__dot">
          <span className="term-fab__ping" />
          <span className="term-fab__core" />
        </span>
        <TerminalIcon />
        {dannTerminals.length > 1 && (
          <span className="term-fab__count">{dannTerminals.length}</span>
        )}
      </IconButton>

      {open && (
        <div className="term-overlay" onClick={() => setOpen(false)}>
          <Card className="term-modal">
            <div onClick={(e) => e.stopPropagation()} className="term-modal__inner">
              <div className="term-modal__head">
                <Tabs
                  size="sm"
                  label="Terminal sessions"
                  tabs={dannTerminals.map((t) => ({ id: t.session_id, label: label(t) }))}
                  active={selected.session_id}
                  onChange={setSelectedId}
                />
                <IconButton label="Close" onClick={() => setOpen(false)}>×</IconButton>
              </div>
              <div className="term-modal__body">
                <Suspense fallback={<div className="term-modal__loading">Loading terminal…</div>}>
                  <TerminalPane key={selected.session_id} sessionId={selected.session_id} isActive />
                </Suspense>
              </div>
            </div>
          </Card>
        </div>
      )}
    </>
  )
}
