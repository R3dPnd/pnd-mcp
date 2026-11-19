import { useState } from 'react'
import { Button, IconButton } from 'pnd-lib-react'
import { useDannStore } from '../hooks/useDannState'
import { api } from '../lib/api'
import type { PipelineStage } from '../types'

// ── Mini orb ──────────────────────────────────────────────────────────────────

function MiniOrb({ stage }: { stage: PipelineStage }) {
  return <div className={`voice-mini voice-mini--${stage}`} />
}

// ── Stage text ────────────────────────────────────────────────────────────────

const STAGE_LABEL: Record<PipelineStage, string> = {
  idle:      'Waiting',
  wake:      'Wake!',
  recording: 'Listening',
  thinking:  'Thinking',
  speaking:  'Speaking',
}

// ── Icons ─────────────────────────────────────────────────────────────────────

function MicOnIcon() {
  return (
    <svg viewBox="0 0 24 24" className="voice-icon" fill="currentColor">
      <path d="M12 14a3 3 0 0 0 3-3V5a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.93V20H9v2h6v-2h-2v-2.07A7 7 0 0 0 19 11h-2z"/>
    </svg>
  )
}

function MicOffIcon() {
  return (
    <svg viewBox="0 0 24 24" className="voice-icon" fill="currentColor">
      <path d="M19 11h-1.7c0 .74-.16 1.43-.43 2.05l1.23 1.23c.56-.98.9-2.09.9-3.28zm-4.02.17c0-.06.02-.11.02-.17V5c0-1.66-1.34-3-3-3S9 3.34 9 5v.18l5.98 5.99zM4.27 3 3 4.27l6.01 6.01V11c0 1.66 1.33 3 2.99 3 .22 0 .44-.03.65-.08l1.66 1.66c-.71.33-1.5.52-2.31.52-2.76 0-5.3-2.1-5.3-5.1H5c0 3.41 2.72 6.23 6 6.72V20H9v2h6v-2h-2v-2.28c.91-.13 1.77-.45 2.54-.9L19.73 21 21 19.73 4.27 3z"/>
    </svg>
  )
}

// ── Widget ────────────────────────────────────────────────────────────────────

export function VoiceWidget() {
  const pipelineStage  = useDannStore((s) => s.pipelineStage)
  const liveResponse   = useDannStore((s) => s.liveResponse)
  const wakePhrase     = useDannStore((s) => s.persona.wake_phrase)
  const personaName = useDannStore((s) => s.persona.name)
  const pendingStt     = useDannStore((s) => s._pendingStt)
  const voiceListening = useDannStore((s) => s.voiceListening)
  const running        = useDannStore((s) => s.running)

  const [triggering, setTriggering] = useState(false)
  const [toggling, setToggling]     = useState(false)

  const inSession = pipelineStage !== 'idle'
  const stageLabel = STAGE_LABEL[pipelineStage]

  // Pick the most informative text to show
  const displayText =
    pipelineStage === 'speaking' && liveResponse  ? liveResponse :
    pipelineStage === 'thinking' && pendingStt     ? `"${pendingStt}"` :
    pipelineStage === 'recording'                  ? '' :
    pipelineStage === 'wake'                       ? 'Session starting…' :
    voiceListening && running                      ? `Say '${wakePhrase}' to begin` :
    ''

  async function handleTrigger() {
    setTriggering(true)
    try { await api.triggerVoice() } catch { /* silent */ } finally { setTriggering(false) }
  }

  async function handleToggleMic() {
    setToggling(true)
    try {
      if (voiceListening) await api.disableVoice()
      else await api.enableVoice()
    } catch { /* silent */ } finally { setToggling(false) }
  }

  return (
    <div className="voice-widget">

      {/* Stage orb */}
      <MiniOrb stage={running && voiceListening ? pipelineStage : 'idle'} />

      {/* Stage label */}
      <span className={`voice-widget__stage ${running && voiceListening ? `voice-widget__stage--${pipelineStage}` : ''}`}>
        {running ? (voiceListening ? stageLabel : 'Off') : 'Offline'}
      </span>

      {/* Separator */}
      <span className="voice-widget__sep">|</span>

      {/* Live text preview */}
      <span className="voice-widget__text">
        {displayText}
        {pipelineStage === 'speaking' && liveResponse && (
          <span className="voice-caret">▋</span>
        )}
      </span>

      {/* Controls */}
      <div className="voice-widget__controls">
        {/* Enable listening — shown when voice is off and the persona is running */}
        {!inSession && !voiceListening && running && (
          <Button onClick={handleToggleMic} disabled={toggling}>
            {toggling ? '…' : 'Enable'}
          </Button>
        )}

        {/* Talk button — only shown when idle and listening */}
        {!inSession && voiceListening && running && (
          <Button onClick={handleTrigger} disabled={triggering}>
            {triggering ? '…' : 'Talk'}
          </Button>
        )}

        {/* Mic toggle */}
        <IconButton
          label={!running ? `${personaName} not running` : voiceListening ? 'Mute' : 'Unmute'}
          active={voiceListening && running}
          onClick={handleToggleMic}
          disabled={toggling || inSession || !running}
        >
          {voiceListening && running ? <MicOnIcon /> : <MicOffIcon />}
        </IconButton>
      </div>
    </div>
  )
}
