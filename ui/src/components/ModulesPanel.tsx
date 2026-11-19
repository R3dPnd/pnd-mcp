import { useState } from 'react'
import { Banner, Button, Card, EmptyState, Tag } from 'pnd-lib-react'
import type { Module } from '../types'
import { useDannStore } from '../hooks/useDannState'
import { api } from '../lib/api'

function statusBadge(mod: Module): { label: string; tone: 'muted' | 'blue' } {
  if (mod.always_on) return { label: 'Always on', tone: 'muted' }
  if (mod.enabled) return { label: 'Active', tone: 'blue' }
  return { label: 'Available', tone: 'muted' }
}

function ModuleCard({ mod }: { mod: Module }) {
  const setModuleEnabled = useDannStore((s) => s.setModuleEnabled)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const badge = statusBadge(mod)

  const toggle = async () => {
    setPending(true)
    setError(null)
    try {
      if (mod.enabled) {
        await api.disableModule(mod.name)
        setModuleEnabled(mod.name, false)
      } else {
        await api.enableModule(mod.name)
        setModuleEnabled(mod.name, true)
      }
    } catch {
      setError(`Could not ${mod.enabled ? 'stop' : 'start'} '${mod.name}'.`)
    } finally {
      setPending(false)
    }
  }

  return (
    <Card className={`mod-card${mod.enabled ? ' is-on' : ''}`}>
      <div className="mod-card__row">
        <span className={`mod-card__dot${mod.enabled ? ' is-on pulse-dot' : ''}`} />

        <div className="mod-card__main">
          <span className="mod-card__name">{mod.name}</span>
          <span className="mod-card__desc" title={mod.description}>
            {mod.description}
          </span>
        </div>

        <Tag tone={badge.tone}>{badge.label}</Tag>

        {!mod.always_on && (
          <Button variant={mod.enabled ? 'ghost' : 'primary'} onClick={toggle} disabled={pending}>
            {pending ? '…' : mod.enabled ? 'Stop' : 'Start'}
          </Button>
        )}
      </div>

      {error && <Banner tone="error">{error}</Banner>}
    </Card>
  )
}

export function ModulesPanel() {
  const personaName = useDannStore((s) => s.persona.name)
  const modules = useDannStore((s) => s.modules)

  if (modules.length === 0) {
    return (
      <EmptyState center>
        No modules configured.
        <br />
        Modules are listed under mcp.servers in config.yaml.
      </EmptyState>
    )
  }

  return (
    <div className="content-list">
      <p className="content-intro">
        Optional modules start on demand — {personaName} enables one itself the first time a turn needs it,
        or start one here yourself.
      </p>
      {modules.map((mod) => (
        <ModuleCard key={mod.name} mod={mod} />
      ))}
    </div>
  )
}
