import { useEffect, useState } from 'react'
import { Banner, Button, Card, EmptyState, IconButton, Tag, TextField, TextInput, relTime } from 'pnd-lib-react'
import type { FocusArea, FocusAreaNote } from '../types'
import { useDannStore } from '../hooks/useDannState'
import { api } from '../lib/api'

function NoteCard({ note, onDelete }: { note: FocusAreaNote; onDelete: () => void }) {
  const [expanded, setExpanded] = useState(false)
  const long = note.content.length > 140 || note.content.includes('\n')

  return (
    <Card className="fa-note">
      <button
        type="button"
        onClick={() => long && setExpanded((v) => !v)}
        className={`fa-note__body${long ? ' is-long' : ''}${expanded ? ' is-expanded' : ''}`}
      >
        <span className="fa-note__title">{note.title}</span>
        <span className="fa-note__text">{note.content}</span>
      </button>
      <div className="fa-note__side">
        <span className="fa-note__time">{relTime(note.modified_at * 1000)}</span>
        <IconButton label="Delete note" title="Delete note" onClick={onDelete}>
          ×
        </IconButton>
      </div>
    </Card>
  )
}

function AddNoteForm({ onAdd }: { onAdd: (title: string, content: string) => Promise<void> }) {
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [saving, setSaving] = useState(false)

  const submit = async () => {
    if (!content.trim() || saving) return
    setSaving(true)
    try {
      await onAdd(title.trim(), content.trim())
      setTitle('')
      setContent('')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card className="fa-add">
      <TextInput value={title} onChange={setTitle} placeholder="Optional title" />
      <TextField
        value={content}
        onChange={setContent}
        placeholder="Note content — remembered in every future conversation about this focus area"
        rows={2}
      />
      <Button variant="primary" onClick={submit} disabled={!content.trim() || saving}>
        {saving ? 'Saving…' : 'Add note'}
      </Button>
    </Card>
  )
}

function FocusAreaCard({ area }: { area: FocusArea }) {
  const [expanded, setExpanded] = useState(false)
  const [notes, setNotes] = useState<FocusAreaNote[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const loadNotes = () => {
    api.getFocusAreaNotes(area.name).then(setNotes).catch(() => setError('Could not load notes.'))
  }

  useEffect(() => {
    if (expanded && notes === null) loadNotes()
  }, [expanded]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleAdd = async (title: string, content: string) => {
    setError(null)
    try {
      const note = await api.createFocusAreaNote(area.name, content, title || undefined)
      setNotes((prev) => [note, ...(prev ?? [])])
    } catch {
      setError('Could not save note.')
    }
  }

  const handleDelete = async (filename: string) => {
    setNotes((prev) => prev?.filter((n) => n.filename !== filename) ?? null)
    try {
      await api.deleteFocusAreaNote(area.name, filename)
    } catch {
      setError('Could not delete note — refresh to check.')
    }
  }

  return (
    <Card className="fa-card">
      <button type="button" onClick={() => setExpanded((v) => !v)} className="fa-card__head" aria-expanded={expanded}>
        <span className="fa-card__main">
          <span className="fa-card__name">{area.name}</span>
          <span className="fa-card__desc">{area.description}</span>
        </span>

        {area.module && (
          <span className="fa-card__tag" title={`Backed by the '${area.module}' module`}>
            <Tag tone={area.module_enabled ? 'blue' : 'muted'}>
              {area.module_enabled ? `${area.module} active` : area.module}
            </Tag>
          </span>
        )}

        <svg
          className={`fa-card__chev${expanded ? ' is-open' : ''}`}
          width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {expanded && (
        <div className="fa-card__body">
          {error && <Banner tone="error">{error}</Banner>}
          {notes === null ? (
            <EmptyState>Loading notes…</EmptyState>
          ) : notes.length === 0 ? (
            <EmptyState>No notes yet.</EmptyState>
          ) : (
            <div className="fa-notes">
              {notes.map((note) => (
                <NoteCard key={note.filename} note={note} onDelete={() => handleDelete(note.filename)} />
              ))}
            </div>
          )}
          <AddNoteForm onAdd={handleAdd} />
        </div>
      )}
    </Card>
  )
}

export function FocusAreasPanel() {
  const personaName = useDannStore((s) => s.persona.name)
  const focusAreas = useDannStore((s) => s.focusAreas)

  if (focusAreas.length === 0) {
    return (
      <EmptyState center>
        No focus areas configured.
        <br />
        Add entries under focus_areas in config.yaml.
      </EmptyState>
    )
  }

  return (
    <div className="content-list">
      <p className="content-intro">
        Topics {personaName} leans into — asks follow-ups on, connects new information to. A module badge
        means real data backs it; without one, it's just something {personaName} knows you care about.
        Click a card to see or add its saved notes — permanent context included in every future
        conversation about it.
      </p>
      {focusAreas.map((area) => (
        <FocusAreaCard key={area.name} area={area} />
      ))}
    </div>
  )
}
