import { useEffect, useRef, useState } from 'react'
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { Card, EmptyState, Meter, Panel } from 'pnd-lib-react'
import { api } from '../lib/api'
import { chartColors, chartTooltip } from './MetricsPage'
import type { ResourceStatus, TurnRecord } from '../types'

const POLL_MS = 3000

function formatBytes(bytes: number): string {
  const gb = bytes / (1024 ** 3)
  return gb >= 1 ? `${gb.toFixed(1)} GB` : `${(bytes / (1024 ** 2)).toFixed(0)} MB`
}

function formatMs(ms: number | null | undefined): string {
  return ms == null ? '—' : `${ms.toFixed(0)} ms`
}

function timeUntil(iso: string): string {
  const ms = new Date(iso).getTime() - Date.now()
  if (ms <= 0) return 'expiring'
  const mins = Math.round(ms / 60000)
  return mins < 1 ? '<1 min' : `${mins} min`
}

// ── Gauge card ─────────────────────────────────────────────────────────────────

function GaugeCard({ label, percent, sub }: { label: string; percent: number; sub?: string }) {
  return (
    <Card className="data-stat data-stat--left">
      <Meter label={label} percent={percent} sub={sub} />
    </Card>
  )
}

// ── System panel ───────────────────────────────────────────────────────────────

export default function SystemPanel() {
  const [status, setStatus] = useState<ResourceStatus | null>(null)
  const [turns, setTurns] = useState<TurnRecord[]>([])
  const [error, setError] = useState<string | null>(null)
  const mounted = useRef(true)

  useEffect(() => {
    mounted.current = true
    const poll = () => {
      Promise.all([api.getResourceStatus(), api.getRecentTurns(30)])
        .then(([s, t]) => {
          if (!mounted.current) return
          setStatus(s)
          setTurns(t)
          setError(null)
        })
        .catch(() => { if (mounted.current) setError('Could not reach the backend.') })
    }
    poll()
    const interval = setInterval(poll, POLL_MS)
    return () => { mounted.current = false; clearInterval(interval) }
  }, [])

  if (error && !status) {
    return <EmptyState center>{error}</EmptyState>
  }
  if (!status) {
    return <EmptyState center>Loading system status…</EmptyState>
  }

  const { memory, cpu, gpu, ollama, turns: turnStats } = status
  const model = ollama?.models?.[0]

  const latencyData = turns.map((t, i) => ({
    index: i,
    stt: t.stt_ms ?? null,
    llm: t.llm_ms ?? null,
    tts: t.tts_ms ?? null,
    chat: t.latency_ms ?? null,
  }))

  const colors = chartColors()
  const tooltipStyle = chartTooltip(colors)

  return (
    <div className="data-page">
      {/* Top gauges */}
      <div className="data-cols data-cols--4">
        <GaugeCard
          label="Memory"
          percent={memory.percent}
          sub={`${formatBytes(memory.used_bytes)} / ${formatBytes(memory.total_bytes)}`}
        />
        <GaugeCard
          label="CPU"
          percent={cpu.percent}
          sub={`${cpu.core_count} cores`}
        />
        {gpu?.gpus?.[0] ? (
          <GaugeCard
            label="GPU"
            percent={gpu.gpus[0].utilization_percent}
            sub={`${gpu.gpus[0].name} — ${formatBytes(gpu.gpus[0].memory_used_mb * 1024 * 1024)} / ${formatBytes(gpu.gpus[0].memory_total_mb * 1024 * 1024)}`}
          />
        ) : (
          <Card className="data-stat data-stat--center">
            <span className="data-stat__label">GPU</span>
            <span className="data-stat__hint">Not available on this machine</span>
          </Card>
        )}
        <Card className="data-stat data-stat--left">
          <span className="data-stat__label">Ollama</span>
          {model ? (
            <>
              <div className="data-stat__model" title={model.name}>{model.name}</div>
              <div className="data-stat__hint">
                {formatBytes(model.size)} resident · unloads in {timeUntil(model.expires_at)}
              </div>
            </>
          ) : (
            <div className="data-stat__hint">No model currently loaded</div>
          )}
        </Card>
      </div>

      {/* Per-core CPU */}
      {cpu.per_core_percent.length > 1 && (
        <Panel title="Per-core CPU">
          <ResponsiveContainer width="100%" height={120}>
            <BarChart
              data={cpu.per_core_percent.map((p, i) => ({ core: `${i}`, percent: p }))}
              margin={{ top: 0, right: 0, left: -20, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} />
              <XAxis dataKey="core" tick={{ fontSize: 10, fill: colors.axis }} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: colors.axis }} />
              <Tooltip {...tooltipStyle} formatter={(v: number) => [`${v.toFixed(0)}%`, 'Load']} />
              <Bar dataKey="percent" fill={colors.accent} radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Panel>
      )}

      {/* Turn latency averages */}
      <div className="data-cols data-cols--5">
        {[
          { label: 'STT', value: turnStats.avg_stt_ms },
          { label: 'LLM', value: turnStats.avg_llm_ms },
          { label: 'TTS', value: turnStats.avg_tts_ms },
          { label: 'Claude', value: turnStats.avg_code_ms },
          { label: 'Chat', value: turnStats.avg_chat_latency_ms },
        ].map(({ label, value }) => (
          <Card key={label} className="data-stat">
            <div className="data-stat__value">{formatMs(value)}</div>
            <div className="data-stat__label">avg {label}</div>
          </Card>
        ))}
      </div>

      {/* Latency over recent turns */}
      {latencyData.length > 1 && (
        <Panel title={`Latency — last ${latencyData.length} turns (${turnStats.sample_count} in buffer)`}>
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={latencyData} margin={{ top: 0, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} />
              <XAxis dataKey="index" tick={{ fontSize: 10, fill: colors.axis }} />
              <YAxis width={56} tick={{ fontSize: 10, fill: colors.axis }} unit="ms" />
              <Tooltip {...tooltipStyle} />
              <Line type="monotone" dataKey="stt" name="STT" stroke={colors.accent} dot={false} connectNulls />
              <Line type="monotone" dataKey="llm" name="LLM" stroke={colors.green} dot={false} connectNulls />
              <Line type="monotone" dataKey="tts" name="TTS" stroke={colors.orange} dot={false} connectNulls />
              <Line type="monotone" dataKey="chat" name="Chat" stroke={colors.violet} dot={false} connectNulls />
            </LineChart>
          </ResponsiveContainer>
        </Panel>
      )}

      {turnStats.sample_count === 0 && (
        <EmptyState center>No turns recorded yet this session.</EmptyState>
      )}
    </div>
  )
}
