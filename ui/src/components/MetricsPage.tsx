import { useEffect, useState } from 'react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from 'recharts'
import { Card, EmptyState, Panel } from 'pnd-lib-react'
import { api } from '../lib/api'
import { useDannStore } from '../hooks/useDannState'
import type { MetricSummary, ProjectMetric } from '../types'

/** Chart colours come from the active theme's CSS tokens; the fallbacks are the glass values. */
export function chartColors() {
  const css = typeof document === 'undefined' ? null : getComputedStyle(document.documentElement)
  const read = (name: string, fallback: string) => css?.getPropertyValue(name).trim() || fallback
  return {
    accent: read('--accent', '#ff2d55'),
    accent2: read('--accent-2', '#8b2cf5'),
    grid: read('--surface-line', 'rgba(255, 255, 255, 0.10)'),
    axis: read('--muted', '#b9a9c6'),
    ink: read('--ink', '#f3eef8'),
    green: read('--green', '#4ade80'),
    red: read('--red', '#ff4d73'),
    orange: read('--orange', '#fbbf24'),
    violet: read('--violet', '#c084fc'),
  }
}

/** Recharts tooltip props styled as a glass surface. */
export function chartTooltip(c: ReturnType<typeof chartColors>) {
  return {
    contentStyle: {
      background: 'rgba(30, 14, 46, 0.92)',
      border: `1px solid ${c.grid}`,
      borderRadius: 12,
      backdropFilter: 'blur(10px)',
      color: c.ink,
    },
    labelStyle: { color: c.ink },
    itemStyle: { color: c.axis },
    cursor: { fill: 'rgba(255, 255, 255, 0.06)' },
  }
}

export default function MetricsPage() {
  const { metricSummary } = useDannStore()
  const [allTime, setAllTime] = useState<MetricSummary | null>(null)
  const [byDay, setByDay] = useState<{ date: string; calls: number }[]>([])
  const [byProject, setByProject] = useState<ProjectMetric[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    Promise.all([
      api.getMetrics('all'),
      api.getCallsByDay(7),
      api.getByProject(),
    ]).then(([summary, days, projects]) => {
      setAllTime(summary)
      setByDay(days)
      setByProject(projects)
    }).catch(() => {}).finally(() => setLoading(false))
  }, [])

  const summary = allTime ?? metricSummary
  const colors = chartColors()

  const successRate = summary && summary.total_calls > 0
    ? `${Math.round((summary.successful_calls / summary.total_calls) * 100)}%`
    : '—'

  const pieData = summary
    ? [
        { name: 'Success', value: summary.successful_calls, color: colors.green },
        { name: 'Error', value: summary.error_calls, color: colors.red },
        { name: 'Empty', value: summary.empty_calls, color: colors.axis },
      ].filter(d => d.value > 0)
    : []

  const tooltipStyle = chartTooltip(colors)

  if (loading) {
    return (
      <EmptyState center>Loading metrics…</EmptyState>
    )
  }

  return (
    <div className="data-page">
      {/* Summary cards */}
      <div className="data-cols data-cols--4">
        {[
          { label: 'Total calls', value: summary?.total_calls ?? 0 },
          { label: 'Projects used', value: summary?.projects_used ?? 0 },
          { label: 'Success rate', value: successRate },
          { label: 'Avg response', value: summary?.avg_response_ms != null ? `${summary.avg_response_ms} ms` : '—' },
        ].map(({ label, value }) => (
          <Card key={label} className="data-stat">
            <div className="data-stat__value data-stat__value--lg">{value}</div>
            <div className="data-stat__label">{label}</div>
          </Card>
        ))}
      </div>

      {/* Calls per day */}
      {byDay.length > 0 && (
        <Panel title="Claude calls per day (last 7 days)">
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={byDay} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: colors.axis }} />
              <YAxis tick={{ fontSize: 11, fill: colors.axis }} allowDecimals={false} />
              <Tooltip {...tooltipStyle} />
              <Bar dataKey="calls" fill={colors.accent} radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Panel>
      )}

      {/* Calls per project */}
      {byProject.length > 0 && (
        <Panel title="Calls per project">
          <ResponsiveContainer width="100%" height={Math.max(160, byProject.length * 28)}>
            <BarChart
              data={byProject}
              layout="vertical"
              margin={{ top: 0, right: 16, left: 8, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} />
              <XAxis type="number" tick={{ fontSize: 11, fill: colors.axis }} allowDecimals={false} />
              <YAxis type="category" dataKey="project" tick={{ fontSize: 11, fill: colors.axis }} width={140} />
              <Tooltip {...tooltipStyle} />
              <Bar dataKey="ok" name="Success" stackId="a" fill={colors.green} />
              <Bar dataKey="error" name="Error" stackId="a" fill={colors.red} />
              <Bar dataKey="empty" name="Empty" stackId="a" fill={colors.axis} radius={[0, 3, 3, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Panel>
      )}

      {/* Status breakdown pie */}
      {pieData.length > 0 && (
        <Panel title="Response status breakdown">
          <ResponsiveContainer width="100%" height={180}>
            <PieChart>
              <Pie
                data={pieData}
                cx="50%"
                cy="50%"
                innerRadius={40}
                outerRadius={70}
                paddingAngle={3}
                dataKey="value"
                label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                labelLine={false}
              >
                {pieData.map((entry) => (
                  <Cell key={entry.name} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip {...tooltipStyle} />
              <Legend wrapperStyle={{ fontSize: 12, color: colors.axis }} />
            </PieChart>
          </ResponsiveContainer>
        </Panel>
      )}

      {summary && summary.total_calls === 0 && (
        <EmptyState center>No Claude calls recorded yet.</EmptyState>
      )}
    </div>
  )
}
