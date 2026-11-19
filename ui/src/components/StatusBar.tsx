import { useState } from 'react'
import { Button, Tag, type Tone } from 'pnd-lib-react'
import { useDannStore } from '../hooks/useDannState'
import { api } from '../lib/api'
import type { Mode, PipelineStage } from '../types'

interface ModeConfig {
  label: string
  tone: Tone
  dot: boolean
}

function modeConfig(mode: Mode, project: string | null): ModeConfig {
  switch (mode) {
    case 'normal':
      return { label: 'Listening', tone: 'green', dot: true }
    case 'code':
      return { label: `Code${project ? `: ${project}` : ''}`, tone: 'violet', dot: false }
    case 'idle':
    default:
      return { label: 'Idle', tone: 'muted', dot: false }
  }
}

const STAGE_CONFIG: Record<PipelineStage, { label: string; tone: Tone }> = {
  idle:        { label: '',            tone: 'muted' },
  wake:        { label: '⚡ Wake',     tone: 'orange' },
  recording:   { label: '● REC',       tone: 'red' },
  thinking:    { label: '… Thinking',  tone: 'blue' },
  speaking:    { label: '▶ Speaking',  tone: 'green' },
}

export function StatusBar() {
  const personaName = useDannStore((s) => s.persona.name)
  const mode = useDannStore((s) => s.mode)
  const project = useDannStore((s) => s.project)
  const wsConnected = useDannStore((s) => s.wsConnected)
  const pipelineStage = useDannStore((s) => s.pipelineStage)
  const modules = useDannStore((s) => s.modules)
  const cfg = modeConfig(mode, project)
  const stage = STAGE_CONFIG[pipelineStage]
  const [restarting, setRestarting] = useState(false)

  // Always-on modules (currently just "projects") are foundational, not
  // interesting to call out here — this is specifically "what did Dann
  // start up on demand for this conversation."
  const activeModules = modules.filter((m) => m.enabled && !m.always_on)

  const handleRestart = async () => {
    if (!window.confirm(`Restart ${personaName}? This will drop any active voice session and reconnect the dashboard.`)) return
    setRestarting(true)
    try {
      await api.restartDann()
    } catch {
      // The process is replacing itself — a failed fetch here is expected, not an error.
    }
  }

  return (
    <header className="status-bar">
      {/* Left: app name */}
      <span className="status-bar__name">{personaName}</span>

      {/* Centre: mode pill + pipeline stage */}
      <div className="status-bar__group">
        <span className="status-bar__mode">
          {cfg.dot && <span className="status-bar__dot pulse-dot" />}
          <Tag tone={cfg.tone}>{cfg.label}</Tag>
        </span>

        {stage.label && (
          <span className="status-bar__stage">
            <Tag tone={stage.tone}>{stage.label}</Tag>
          </span>
        )}
      </div>

      {/* Right: active modules + restart + WS connection indicator */}
      <div className="status-bar__group">
        {activeModules.length > 0 && (
          <div className="status-bar__modules" title={`Modules ${personaName} currently has active`}>
            {activeModules.map((m) => (
              <span key={m.name} className="status-bar__module">
                <span className="status-bar__dot pulse-dot" />
                {m.name}
              </span>
            ))}
          </div>
        )}

        <Button
          variant="link"
          onClick={handleRestart}
          disabled={restarting}
          title={`Restart ${personaName}`}
        >
          {restarting ? 'restarting…' : '⟳'}
        </Button>

        {wsConnected ? (
          <div className="status-bar__conn">
            <span className="status-bar__dot status-bar__dot--ok" />
            connected
          </div>
        ) : (
          <div className="status-bar__conn status-bar__conn--off">
            <span className="status-bar__dot" />
            offline
          </div>
        )}
      </div>
    </header>
  )
}
