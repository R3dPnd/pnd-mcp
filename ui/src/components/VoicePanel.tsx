import { useEffect, useRef, useState } from 'react'
import { Button, Card, ChatMessage, IconButton, Tag, relTime } from 'pnd-lib-react'
import { useDannStore } from '../hooks/useDannState'
import { api } from '../lib/api'
import { StateOrb } from './voice/StateOrb'
import type { PipelineStage, RawEvent, TurnTrace, VoiceTurn } from '../types'

// ── Stage config ──────────────────────────────────────────────────────────────

const STAGE_INFO: Record<PipelineStage, { label: string }> = {
  idle:      { label: 'Listening' },  // + wake phrase, see stageLabel
  wake:      { label: 'Wake word detected' },
  recording: { label: 'Listening…' },
  thinking:  { label: 'Thinking…' },
  speaking:  { label: 'Speaking…' },
}

// ── Stage duration timer ──────────────────────────────────────────────────────

function StageDuration({ stageEnteredAt, stage }: { stageEnteredAt: number; stage: PipelineStage }) {
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    if (stage === 'idle') { setElapsed(0); return }
    const id = setInterval(() => {
      setElapsed(Math.floor((Date.now() - stageEnteredAt) / 100) / 10)
    }, 100)
    return () => clearInterval(id)
  }, [stage, stageEnteredAt])

  if (stage === 'idle' || elapsed < 0.1) return null
  return <span className="voice-duration">{elapsed.toFixed(1)}s</span>
}

// ── Per-turn trace bar ────────────────────────────────────────────────────────

export function TraceBar({ trace }: { trace: TurnTrace }) {
  const steps: { label: string; ms: number | null; tone: string }[] = [
    { label: 'STT',  ms: trace.stt_ms,  tone: 'stt' },
    { label: 'LLM',  ms: trace.llm_ms,  tone: 'llm' },
    { label: 'TTS',  ms: trace.tts_ms,  tone: 'tts' },
    { label: 'CODE', ms: trace.code_ms, tone: 'code' },
  ]
  const visible = steps.filter(s => s.ms != null && s.ms > 0)
  const total = visible.reduce((acc, s) => acc + (s.ms ?? 0), 0)
  const statusTone = trace.status === 'ok' ? 'ok' : trace.status === 'error' ? 'error' : 'idle'

  return (
    <div className="voice-trace">
      {visible.map(s => (
        <span key={s.label} className={`voice-trace__step voice-trace__step--${s.tone}`}>
          {s.label} {s.ms}ms
        </span>
      ))}
      {total > 0 && <span className="voice-trace__total">∑ {total}ms</span>}
      <span className={`voice-trace__status voice-trace__status--${statusTone}`}>{trace.status}</span>
    </div>
  )
}

// ── Turn card ─────────────────────────────────────────────────────────────────

function TurnCard({ turn }: { turn: VoiceTurn }) {
  const [showTrace, setShowTrace] = useState(false)

  return (
    <div className="voice-turn">
      <div className="voice-turn__head">
        <span className="voice-turn__time">{relTime(turn.timestamp.getTime())}</span>
        {turn.mode === 'code' && turn.project && <Tag tone="blue">{turn.project}</Tag>}
        {turn.trace && (
          <Button variant="link" className="voice-turn__trace" onClick={() => setShowTrace(v => !v)}>
            {showTrace ? '▲' : '▼'} trace
          </Button>
        )}
      </div>

      {turn.userText && <ChatMessage role="user">{turn.userText}</ChatMessage>}
      {turn.dannText && <ChatMessage role="assistant">{turn.dannText}</ChatMessage>}

      {showTrace && turn.trace && <TraceBar trace={turn.trace} />}
    </div>
  )
}

// ── Debug event log ───────────────────────────────────────────────────────────

function DebugLog({ events }: { events: RawEvent[] }) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'instant' })
  }, [events.length])

  return (
    <div className="voice-debug">
      {events.slice(-100).map((e, i) => (
        <div key={i} className="voice-debug__row">
          <span className="voice-debug__ts">
            {new Date(e.ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
          </span>
          <span className="voice-debug__type">{e.type}</span>
          <span className="voice-debug__summary">{e.summary}</span>
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  )
}

// ── Mic icons ─────────────────────────────────────────────────────────────────

function MicOn()  {
  return (
    <svg viewBox="0 0 24 24" className="voice-icon" fill="currentColor">
      <path d="M12 14a3 3 0 0 0 3-3V5a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.93V20H9v2h6v-2h-2v-2.07A7 7 0 0 0 19 11h-2z"/>
    </svg>
  )
}
function MicOff() {
  return (
    <svg viewBox="0 0 24 24" className="voice-icon" fill="currentColor">
      <path d="M19 11h-1.7c0 .74-.16 1.43-.43 2.05l1.23 1.23c.56-.98.9-2.09.9-3.28zm-4.02.17c0-.06.02-.11.02-.17V5c0-1.66-1.34-3-3-3S9 3.34 9 5v.18l5.98 5.99zM4.27 3 3 4.27l6.01 6.01V11c0 1.66 1.33 3 2.99 3 .22 0 .44-.03.65-.08l1.66 1.66c-.71.33-1.5.52-2.31.52-2.76 0-5.3-2.1-5.3-5.1H5c0 3.41 2.72 6.23 6 6.72V20H9v2h6v-2h-2v-2.28c.91-.13 1.77-.45 2.54-.9L19.73 21 21 19.73 4.27 3z"/>
    </svg>
  )
}

// ── Main panel ────────────────────────────────────────────────────────────────

export function VoicePanel() {
  const voiceTurns     = useDannStore(s => s.voiceTurns)
  const pipelineStage  = useDannStore(s => s.pipelineStage)
  const stageEnteredAt = useDannStore(s => s.stageEnteredAt)
  const pendingStt     = useDannStore(s => s._pendingStt)
  const liveResponse   = useDannStore(s => s.liveResponse)
  const voiceListening = useDannStore(s => s.voiceListening)
  const running        = useDannStore(s => s.running)
  const wsConnected    = useDannStore(s => s.wsConnected)
  const rawEvents      = useDannStore(s => s.rawEvents)
  const prependTurns   = useDannStore(s => s.prependTurns)

  const [collapsed, setCollapsed]   = useState(false)
  const [debugOpen, setDebugOpen]   = useState(false)
  const [triggering, setTriggering] = useState(false)
  const [toggling, setToggling]     = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  const inSession = pipelineStage !== 'idle'
  const active    = running && voiceListening
  const stageInfo = STAGE_INFO[pipelineStage]
  const wakePhrase = useDannStore(s => s.persona.wake_phrase)
  const personaName = useDannStore((s) => s.persona.name)
  const stageLabel = pipelineStage === 'idle' ? `Listening for '${wakePhrase}'` : stageInfo.label

  // Load persisted history once on mount
  useEffect(() => {
    api.getHistory(150).then(records => {
      if (!records.length) return
      const turns: VoiceTurn[] = records
        .filter(r => r['user_text'] || r['dann_text'])
        .map(r => ({
          id: `hist-${r['started_at'] ?? r['timestamp']}-${r['session_id'] ?? Math.random()}`,
          sessionId: (r['session_id'] as string | null) ?? null,
          timestamp: new Date(r['timestamp'] as string),
          userText:  (r['user_text']  as string) ?? '',
          dannText:  (r['dann_text']  as string) ?? '',
          mode:      ((r['mode'] as string) ?? 'normal') as 'normal' | 'code',
          project:   r['project'] as string | undefined,
          trace: (r['stt_ms'] != null || r['llm_ms'] != null) ? {
            stt_ms:  (r['stt_ms']  as number | null) ?? null,
            llm_ms:  (r['llm_ms']  as number | null) ?? null,
            tts_ms:  (r['tts_ms']  as number | null) ?? null,
            code_ms: (r['code_ms'] as number | null) ?? null,
            status:  (r['status']  as string)        ?? 'ok',
          } : undefined,
        }))
      turns.reverse() // API returns newest-first; display oldest-first
      prependTurns(turns)
    }).catch(() => {})
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Scroll to bottom on new content
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [voiceTurns.length, liveResponse])

  async function handleTrigger() {
    setTriggering(true)
    try { await api.triggerVoice() } catch { /* silent */ } finally { setTriggering(false) }
  }

  async function handleToggle() {
    setToggling(true)
    try {
      if (voiceListening) await api.disableVoice()
      else await api.enableVoice()
    } catch { /* silent */ } finally { setToggling(false) }
  }

  // Collapsed — thin strip with status dot and expand button
  if (collapsed) {
    return (
      <Card className="voice-panel voice-panel--collapsed">
        <IconButton label="Expand voice panel" onClick={() => setCollapsed(false)}>‹</IconButton>
        <span className={`voice-dot ${active ? 'is-active' : wsConnected ? '' : 'is-offline'}`} />
      </Card>
    )
  }

  return (
    <Card className="voice-panel">

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div className="voice-panel__head">
        <span className="voice-panel__title">Voice</span>
        <div className="voice-panel__head-actions">
          {!wsConnected && <span className="voice-panel__offline">OFFLINE</span>}
          <IconButton label="Collapse panel" onClick={() => setCollapsed(true)}>›</IconButton>
        </div>
      </div>

      {/* ── Orb + stage ────────────────────────────────────────────────────── */}
      <div className="voice-stage">
        <StateOrb stage={pipelineStage} active={active} />

        <div className="voice-stage__row">
          <span className={`voice-stage__label ${active ? `voice-stage__label--${pipelineStage}` : ''}`}>
            {!running ? 'Offline' : !voiceListening ? 'Voice off' : stageLabel}
          </span>
          {active && (
            <StageDuration stageEnteredAt={stageEnteredAt} stage={pipelineStage} />
          )}
        </div>

        {pipelineStage === 'thinking' && pendingStt && (
          <span className="voice-stage__stt">"{pendingStt}"</span>
        )}

        {/* Controls */}
        <div className="voice-stage__controls">
          {pipelineStage === 'idle' && voiceListening && running && (
            <Button onClick={handleTrigger} disabled={triggering}>
              {triggering ? '…' : 'Talk'}
            </Button>
          )}

          <IconButton
            label={!running ? `${personaName} not running` : voiceListening ? 'Mute' : 'Unmute'}
            active={voiceListening && running}
            onClick={handleToggle}
            disabled={toggling || inSession || !running}
          >
            {voiceListening && running ? <MicOn /> : <MicOff />}
          </IconButton>
        </div>
      </div>

      {/* ── Conversation history ────────────────────────────────────────────── */}
      <div className="voice-history">
        {voiceTurns.length === 0 && !liveResponse ? (
          <p className="voice-history__empty">No conversations yet</p>
        ) : (
          voiceTurns.map(turn => <TurnCard key={turn.id} turn={turn} />)
        )}

        {/* Live streaming response */}
        {liveResponse && (
          <div className="voice-turn">
            {pendingStt && (
              <div className="voice-turn__pending">
                <ChatMessage role="user">{pendingStt}</ChatMessage>
              </div>
            )}
            <ChatMessage role="assistant">
              {liveResponse}
              <span className="voice-caret">▋</span>
            </ChatMessage>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* ── Debug panel (collapsible) ───────────────────────────────────────── */}
      <div className="voice-events">
        <button className="voice-events__toggle" onClick={() => setDebugOpen(v => !v)}>
          <span>EVENTS</span>
          <span className="voice-events__count">{debugOpen ? '▼' : '▲'} {rawEvents.length}</span>
        </button>
        {debugOpen && <DebugLog events={rawEvents} />}
      </div>
    </Card>
  )
}
