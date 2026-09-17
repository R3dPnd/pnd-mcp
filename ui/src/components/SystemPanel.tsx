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
import { api } from '../lib/api'
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
  const color = percent >= 90 ? '#ef4444' : percent >= 70 ? '#f59e0b' : '#22c55e'
  return (
    <div className="bg-gray-800 rounded-lg p-3">
      <div className="flex items-baseline justify-between">
        <span className="text-xs text-gray-400">{label}</span>
        <span className="text-lg font-bold text-white">{percent.toFixed(0)}%</span>
      </div>
      <div className="mt-2 h-1.5 bg-gray-700 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${Math.min(100, percent)}%`, backgroundColor: color }}
        />
      </div>
      {sub && <div className="text-xs text-gray-500 mt-1">{sub}</div>}
    </div>
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
    return <div className="p-4 text-center text-gray-500 py-12">{error}</div>
  }
  if (!status) {
    return <div className="flex items-center justify-center h-64 text-gray-400">Loading system status…</div>
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

  const tooltipStyle = {
    contentStyle: { backgroundColor: '#1f2937', border: 'none', borderRadius: 6 },
    labelStyle: { color: '#e5e7eb' },
  }

  return (
    <div className="p-4 space-y-6 overflow-y-auto">
      {/* Top gauges */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
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
          <div className="bg-gray-800 rounded-lg p-3 flex flex-col justify-center items-center text-center">
            <span className="text-xs text-gray-400">GPU</span>
            <span className="text-xs text-gray-500 mt-1">Not available on this machine</span>
          </div>
        )}
        <div className="bg-gray-800 rounded-lg p-3">
          <span className="text-xs text-gray-400">Ollama</span>
          {model ? (
            <>
              <div className="text-sm font-semibold text-white mt-1 truncate" title={model.name}>{model.name}</div>
              <div className="text-xs text-gray-500 mt-1">
                {formatBytes(model.size)} resident · unloads in {timeUntil(model.expires_at)}
              </div>
            </>
          ) : (
            <div className="text-xs text-gray-500 mt-1">No model currently loaded</div>
          )}
        </div>
      </div>

      {/* Per-core CPU */}
      {cpu.per_core_percent.length > 1 && (
        <div className="bg-gray-800 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-gray-300 mb-3">Per-core CPU</h3>
          <ResponsiveContainer width="100%" height={120}>
            <BarChart
              data={cpu.per_core_percent.map((p, i) => ({ core: `${i}`, percent: p }))}
              margin={{ top: 0, right: 0, left: -20, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="core" tick={{ fontSize: 10, fill: '#9ca3af' }} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: '#9ca3af' }} />
              <Tooltip {...tooltipStyle} formatter={(v: number) => [`${v.toFixed(0)}%`, 'Load']} />
              <Bar dataKey="percent" fill="#3b82f6" radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Turn latency averages */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {[
          { label: 'STT', value: turnStats.avg_stt_ms },
          { label: 'LLM', value: turnStats.avg_llm_ms },
          { label: 'TTS', value: turnStats.avg_tts_ms },
          { label: 'Claude', value: turnStats.avg_code_ms },
          { label: 'Chat', value: turnStats.avg_chat_latency_ms },
        ].map(({ label, value }) => (
          <div key={label} className="bg-gray-800 rounded-lg p-3 text-center">
            <div className="text-lg font-bold text-white">{formatMs(value)}</div>
            <div className="text-xs text-gray-400 mt-1">avg {label}</div>
          </div>
        ))}
      </div>

      {/* Latency over recent turns */}
      {latencyData.length > 1 && (
        <div className="bg-gray-800 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-gray-300 mb-3">
            Latency — last {latencyData.length} turns ({turnStats.sample_count} in buffer)
          </h3>
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={latencyData} margin={{ top: 0, right: 8, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="index" tick={{ fontSize: 10, fill: '#9ca3af' }} />
              <YAxis tick={{ fontSize: 10, fill: '#9ca3af' }} unit="ms" />
              <Tooltip {...tooltipStyle} />
              <Line type="monotone" dataKey="stt" name="STT" stroke="#3b82f6" dot={false} connectNulls />
              <Line type="monotone" dataKey="llm" name="LLM" stroke="#22c55e" dot={false} connectNulls />
              <Line type="monotone" dataKey="tts" name="TTS" stroke="#f59e0b" dot={false} connectNulls />
              <Line type="monotone" dataKey="chat" name="Chat" stroke="#a855f7" dot={false} connectNulls />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {turnStats.sample_count === 0 && (
        <div className="text-center text-gray-500 py-8">No turns recorded yet this session.</div>
      )}
    </div>
  )
}
