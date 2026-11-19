import { useEffect, useState } from 'react'
import {
  Banner, Button, ChatMessage, Composer, EmptyState, IconButton, MessageList, Select, Spinner, Tag,
  TextInput, ToolActivity, WorkingIndicator, fmtTime, relTime,
} from 'pnd-lib-react'
import { api } from '../lib/api'
import { useDannStore } from '../hooks/useDannState'
import type { FocusArea, WorkStream } from '../types'

// What the typing indicator says while a reply is running a tool.
const TOOL_ACTIVITY: Record<string, string> = {
  web_search: 'searching the web…',
  search_notes: 'checking your notes…',
  get_note: 'reading your notes…',
  list_areas: 'checking your notes…',
  add_reminder: 'saving a reminder…',
  list_reminders: 'checking your reminders…',
  open_app: 'opening the app…',
  get_volume: 'checking the volume…',
  set_volume: 'setting the volume…',
}

function activityLabel(tool: string | undefined): string {
  if (!tool) return 'thinking…'
  return TOOL_ACTIVITY[tool] ?? `using ${tool.replace(/_/g, ' ')}…`
}

function SpeakerIcon({ playing }: { playing: boolean }) {
  return playing ? (
    <svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor" aria-hidden>
      <rect x="4" y="4" width="8" height="8" rx="1" />
    </svg>
  ) : (
    <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden>
      <path d="M2.5 6h2.5l3.5-3v10l-3.5-3H2.5z" fill="currentColor" stroke="none" />
      <path d="M11 5.5a3.5 3.5 0 0 1 0 5M12.8 3.8a6 6 0 0 1 0 8.4" strokeLinecap="round" />
    </svg>
  )
}

function NewStreamForm({
  focusAreas,
  onCreate,
  onCancel,
}: {
  focusAreas: FocusArea[]
  onCreate: (focusArea: string, title: string) => void
  onCancel: () => void
}) {
  const [focusArea, setFocusArea] = useState(focusAreas[0]?.name ?? '')
  const [title, setTitle] = useState('')

  return (
    <div className="chat-newform">
      <Select
        label="Focus area"
        value={focusArea}
        onChange={setFocusArea}
        options={focusAreas.map((a) => ({ value: a.name, label: a.name }))}
      />
      <TextInput label="Title" value={title} onChange={setTitle} placeholder="Optional title" />
      <div className="chat-newform__actions">
        <Button variant="primary" onClick={() => focusArea && onCreate(focusArea, title)} disabled={!focusArea}>
          Create
        </Button>
        <Button onClick={onCancel}>Cancel</Button>
      </div>
    </div>
  )
}

export default function ChatPanel() {
  const personaName = useDannStore((s) => s.persona.name)
  const chatActivity = useDannStore((s) => s.chatActivity)
  const chatPostedCount = useDannStore((s) => s.chatPostedCount)
  const speechDoneCount = useDannStore((s) => s.speechDoneCount)
  const [readingIndex, setReadingIndex] = useState<number | null>(null)
  const [streams, setStreams] = useState<WorkStream[]>([])
  const [focusAreas, setFocusAreas] = useState<FocusArea[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [active, setActive] = useState<WorkStream | null>(null)
  const [showNewForm, setShowNewForm] = useState(false)
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // Bumped when the reader's own action should jump the list to the bottom.
  const [forceKey, setForceKey] = useState(0)

  useEffect(() => {
    api.listStreams().then(setStreams).catch(() => {})
    api.getFocusAreas().then(setFocusAreas).catch(() => {})
  }, [])

  useEffect(() => {
    if (!activeId) { setActive(null); return }
    api.getStream(activeId).then(setActive).catch(() => setActive(null))
  }, [activeId])

  // Something was posted server-side (the morning report, a finished hunt):
  // pick up a new stream and new messages in the open one.
  useEffect(() => {
    if (chatPostedCount === 0) return
    api.listStreams().then(setStreams).catch(() => {})
    if (activeId) api.getStream(activeId).then(setActive).catch(() => {})
  }, [chatPostedCount])

  // Reading finished, was stopped, or this chat was left.
  useEffect(() => setReadingIndex(null), [speechDoneCount, activeId])

  async function toggleReadAloud(index: number, text: string) {
    setError(null)
    try {
      if (readingIndex === index) {
        await api.stopSpeaking()
        setReadingIndex(null)
      } else {
        await api.speak(text)  // replaces anything already being read
        setReadingIndex(index)
      }
    } catch {
      setReadingIndex(null)
      setError(`${personaName} can't read aloud right now — voice is off.`)
    }
  }

  // Opening another chat always starts at the bottom (once its messages have loaded).
  const loadedId = active?.id
  useEffect(() => setForceKey((k) => k + 1), [loadedId])

  async function handleCreate(focusArea: string, title: string) {
    setError(null)
    try {
      const stream = await api.createStream(focusArea, title)
      setStreams((prev) => [stream, ...prev])
      setActiveId(stream.id)
      setShowNewForm(false)
    } catch {
      setError(`Could not create a stream for '${focusArea}'.`)
    }
  }

  async function handleDelete(id: string) {
    await api.deleteStream(id).catch(() => {})
    setStreams((prev) => prev.filter((s) => s.id !== id))
    if (activeId === id) setActiveId(null)
  }

  async function handleClear() {
    if (!activeId) return
    if (!window.confirm(`Clear this conversation? ${personaName} will start fresh with no memory of it.`)) return
    setError(null)
    try {
      const cleared = await api.clearStream(activeId)
      setActive(cleared)
      setStreams((prev) => prev.map((s) => (s.id === cleared.id ? cleared : s)))
    } catch {
      setError('Could not clear this conversation.')
    }
  }

  async function handleSend() {
    const text = input.trim()
    if (!text || !activeId || sending) return
    setSending(true)
    setError(null)
    setInput('')
    setForceKey((k) => k + 1)
    // Optimistic append so the UI feels responsive during the (possibly
    // multi-second) Ollama round trip.
    setActive((prev) =>
      prev ? { ...prev, messages: [...prev.messages, { role: 'user', content: text, ts: Date.now() / 1000 }] } : prev
    )
    try {
      await api.sendChatMessage(activeId, text)
      const fresh = await api.getStream(activeId)
      setActive(fresh)
      setStreams((prev) => {
        const updated = prev.map((s) => (s.id === fresh.id ? fresh : s))
        return updated.sort((a, b) => b.updated_at - a.updated_at)
      })
    } catch {
      setError(`${personaName} could not respond — is Ollama running?`)
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="chat">
      {/* ── Stream list ─────────────────────────────────────────────────── */}
      <div className="chat-streams">
        <div className="chat-streams__head">
          <span className="chat-streams__title">Work Streams</span>
          <Button variant="primary" onClick={() => setShowNewForm((v) => !v)} title="Start a new conversation">
            + New conversation
          </Button>
        </div>

        {showNewForm && (
          <NewStreamForm
            focusAreas={focusAreas}
            onCreate={handleCreate}
            onCancel={() => setShowNewForm(false)}
          />
        )}

        <div className="chat-streams__list">
          {streams.length === 0 ? (
            <EmptyState center>No work streams yet.</EmptyState>
          ) : (
            streams.map((s) => (
              <div key={s.id} className={`chat-stream${s.id === activeId ? ' is-active' : ''}`}>
                <button type="button" className="chat-stream__open" onClick={() => setActiveId(s.id)}>
                  <span className="chat-stream__name">
                    {s.pending_job && <span title={s.pending_job.label}><Spinner size="sm" /></span>}
                    <span className="chat-stream__text">{s.title}</span>
                  </span>
                  <span className="chat-stream__meta">
                    {s.title !== s.focus_area && `${s.focus_area} · `}{relTime(s.updated_at * 1000)}
                  </span>
                </button>
                <IconButton label="Delete" className="chat-stream__delete" onClick={() => handleDelete(s.id)}>
                  ×
                </IconButton>
              </div>
            ))
          )}
        </div>
      </div>

      {!active ? (
        <div className="chat-empty">
          <EmptyState center>Select or create a work stream to start chatting with {personaName}.</EmptyState>
        </div>
      ) : (
        <div className="chat-main">
          <div className="chat-head">
            <div className="chat-head__title">
              <span className="chat-head__name">{active.title}</span>
              {active.title !== active.focus_area && <Tag tone="blue">{active.focus_area}</Tag>}
            </div>
            <div className="chat-head__actions">
              <Button onClick={() => setShowNewForm((v) => !v)} title="Start a new conversation">
                New
              </Button>
              <Button
                onClick={handleClear}
                disabled={active.messages.length === 0}
                title={`Clear this conversation's history — ${personaName} starts fresh`}
              >
                Clear
              </Button>
            </div>
          </div>

          <MessageList
            className="chat-messages"
            stickKey={`${active.messages.length}:${sending}`}
            forceKey={forceKey}
            empty={<EmptyState center>No messages yet — say hello.</EmptyState>}
          >
            {active.messages.map((m, i) => (
              <ChatMessage
                key={i}
                role={m.role === 'user' ? 'user' : 'assistant'}
                time={fmtTime(m.ts * 1000)}
                actions={
                  <IconButton
                    label={readingIndex === i ? 'Stop reading' : `Have ${personaName} read this aloud`}
                    active={readingIndex === i}
                    onClick={() => toggleReadAloud(i, m.content)}
                  >
                    <SpeakerIcon playing={readingIndex === i} />
                  </IconButton>
                }
              >
                {m.content}
              </ChatMessage>
            ))}
            {sending && <ToolActivity label={activityLabel(activeId ? chatActivity[activeId] : undefined)} />}
            {!sending && active.pending_job && (
              <WorkingIndicator label={`${active.pending_job.label}…`} startedMs={active.pending_job.started * 1000} />
            )}
          </MessageList>

          {error && <Banner tone="error">{error}</Banner>}

          <div className="chat-composer">
            <Composer
              value={input}
              onChange={setInput}
              onSend={handleSend}
              placeholder={`Message ${personaName}…`}
              disabled={sending}
            />
          </div>
        </div>
      )}
    </div>
  )
}
