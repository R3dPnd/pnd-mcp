import { Card, EmptyState } from 'pnd-lib-react'
import type { Project } from '../types'
import { useDannStore } from '../hooks/useDannState'

function NoteCard({ note }: { note: Project }) {
  return (
    <Card className="note-card">
      <span className="note-card__name">{note.name}</span>
      <span className="note-card__path" title={note.path}>
        {note.path}
      </span>
    </Card>
  )
}

export function NotesPanel() {
  const noteProjects = useDannStore((s) => s.noteProjects)

  if (noteProjects.length === 0) {
    return (
      <EmptyState center>
        No notes repositories found.
        <br />
        Add entries under "notes" in config.yaml.
      </EmptyState>
    )
  }

  return (
    <div className="content-list">
      {noteProjects.map((note) => (
        <NoteCard key={note.name} note={note} />
      ))}
    </div>
  )
}
