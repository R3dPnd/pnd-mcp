import type { PipelineStage } from '../../types'

const EQ_BARS: { delay: string; duration: string }[] = [
  { delay: '0s',    duration: '0.55s' },
  { delay: '0.15s', duration: '0.80s' },
  { delay: '0.05s', duration: '0.50s' },
  { delay: '0.25s', duration: '0.70s' },
  { delay: '0.10s', duration: '0.90s' },
]

export function StateOrb({ stage, active, size = 88 }: { stage: PipelineStage; active: boolean; size?: number }) {
  const style = { '--voice-orb-size': `${size}px` } as React.CSSProperties

  if (!active) return <div className="voice-orb voice-orb--idle" style={style} />

  if (stage === 'speaking') {
    return (
      <div className="voice-eq" style={style}>
        {EQ_BARS.map((b, i) => (
          <div key={i} className="voice-eq__bar" style={{ animationDelay: b.delay, animationDuration: b.duration }} />
        ))}
      </div>
    )
  }

  return <div className={`voice-orb voice-orb--${stage}`} style={style} />
}
