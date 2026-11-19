import { useCallback, useEffect, useRef, useState } from 'react'
import { Button, Checkbox, EmptyState, Select, TextInput, relTime } from 'pnd-lib-react'
import { useDannStore } from '../hooks/useDannState'
import type { LogEntry } from '../types'

const LEVEL_ORDER = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']

function LogRow({ entry }: { entry: LogEntry }) {
  const [expanded, setExpanded] = useState(false)
  const level = LEVEL_ORDER.includes(entry.level) ? entry.level.toLowerCase() : 'debug'

  return (
    <div
      className="log-row"
      onClick={() => entry.detail && setExpanded(e => !e)}
    >
      <div className="log-row__line">
        <span className="log-row__time" title={entry.timestamp}>
          {relTime(entry.timestamp)}
        </span>
        <span className={`log-level log-level--${level}`}>{entry.level}</span>
        <span className="log-row__module">{entry.module}</span>
        <span className="log-row__msg">{entry.message}</span>
        {entry.detail && (
          <span className="log-row__chevron">{expanded ? '▲' : '▼'}</span>
        )}
      </div>

      {expanded && entry.detail && (
        <pre className="log-row__detail">{entry.detail}</pre>
      )}
    </div>
  )
}

export default function LogPanel() {
  const { logEntries, unreadErrors, clearUnreadErrors } = useDannStore()
  const [open, setOpen] = useState(false)
  const [minLevel, setMinLevel] = useState(2) // default: WARNING (index 2)
  const [moduleFilter, setModuleFilter] = useState('')
  const [search, setSearch] = useState('')
  const [errorsOnly, setErrorsOnly] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  const effectiveMinLevel = errorsOnly ? 3 : minLevel // ERROR when errors-only

  const filtered = logEntries.filter(e => {
    const rank = LEVEL_ORDER.indexOf(e.level)
    if (rank < effectiveMinLevel) return false
    if (moduleFilter && e.module !== moduleFilter) return false
    if (search && !e.message.toLowerCase().includes(search.toLowerCase())) return false
    return true
  })

  // Auto-scroll to bottom when panel is open
  useEffect(() => {
    if (open) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [filtered.length, open])

  const handleOpen = useCallback(() => {
    setOpen(o => {
      if (!o) clearUnreadErrors()
      return !o
    })
  }, [clearUnreadErrors])

  // Collect unique modules for filter checkboxes
  const modules = [...new Set(logEntries.map(e => e.module))].sort()

  const downloadLog = useCallback(() => {
    const text = filtered
      .map(e => `[${e.timestamp}] [${e.level}] [${e.module}] ${e.message}${e.detail ? '\n' + e.detail : ''}`)
      .join('\n')
    const blob = new Blob([text], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `dann-log-${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.txt`
    a.click()
    URL.revokeObjectURL(url)
  }, [filtered])

  return (
    <div className="log-panel">
      {/* Header tab */}
      <button onClick={handleOpen} className="log-head">
        <span>Logs</span>
        {unreadErrors > 0 && <span className="log-head__unread">{unreadErrors}</span>}
        <span className="log-head__chevron">{open ? '▼' : '▲'}</span>
      </button>

      {open && (
        <>
          {/* Filter bar */}
          <div className="log-filters">
            {/* Level slider */}
            <div className="log-filters__level">
              <span className="log-filters__label">Level:</span>
              <input
                type="range"
                min={0}
                max={4}
                value={minLevel}
                onChange={e => setMinLevel(Number(e.target.value))}
                disabled={errorsOnly}
                aria-label="Minimum log level"
              />
              <span className="log-filters__value">{LEVEL_ORDER[minLevel]}</span>
            </div>

            {/* Module select */}
            {modules.length > 0 && (
              <Select
                value={moduleFilter}
                onChange={setModuleFilter}
                options={[{ value: '', label: 'All modules' }, ...modules.map(m => ({ value: m, label: m }))]}
              />
            )}

            {/* Search */}
            <TextInput placeholder="Search…" value={search} onChange={setSearch} />

            {/* Errors only toggle */}
            <Checkbox checked={errorsOnly} onChange={setErrorsOnly}>Errors only</Checkbox>

            <span className="log-filters__count">{filtered.length} entries</span>

            {/* Download */}
            <Button variant="link" onClick={downloadLog}>Download</Button>
          </div>

          {/* Log entries */}
          <div className="log-entries">
            {filtered.length === 0 ? (
              <EmptyState center>No log entries match the current filters.</EmptyState>
            ) : (
              filtered.map((entry, i) => <LogRow key={i} entry={entry} />)
            )}
            <div ref={bottomRef} />
          </div>
        </>
      )}
    </div>
  )
}
