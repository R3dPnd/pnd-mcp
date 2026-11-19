import { useState } from 'react'
import { Banner, Button, Card, CopyButton, IconButton, Panel, Spinner, Tag, TextField } from 'pnd-lib-react'
import type { Tone } from 'pnd-lib-react'
import { api } from '../lib/api'

interface Section {
  id: string
  title: string
  content: string
}

const DEFAULT_SECTIONS: Section[] = [
  { id: 'thoughts', title: 'Thoughts', content: '' },
  { id: 'goals',    title: 'Goals',    content: '' },
  { id: 'notes',    title: 'Notes',    content: '' },
]

interface BuildResult {
  recommended_model: string
  prompt: string
  reasoning: string
}

const MODEL_LABELS: Record<string, string> = {
  'claude-opus-4-6':           'Opus 4.6',
  'claude-sonnet-4-6':         'Sonnet 4.6',
  'claude-haiku-4-5-20251001': 'Haiku 4.5',
}

const MODEL_TONES: Record<string, Tone> = {
  'claude-opus-4-6':           'violet',
  'claude-sonnet-4-6':         'cyan',
  'claude-haiku-4-5-20251001': 'green',
}

export function PromptBuilderPanel() {
  const [sections, setSections] = useState<Section[]>(DEFAULT_SECTIONS)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<BuildResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const updateSection = (id: string, content: string) => {
    setSections(prev => prev.map(s => s.id === id ? { ...s, content } : s))
  }

  const addSection = () => {
    setSections(prev => [...prev, {
      id: crypto.randomUUID(),
      title: 'Section',
      content: '',
    }])
  }

  const removeSection = (id: string) => {
    setSections(prev => prev.filter(s => s.id !== id))
  }

  const updateTitle = (id: string, title: string) => {
    setSections(prev => prev.map(s => s.id === id ? { ...s, title } : s))
  }

  const hasContent = sections.some(s => s.content.trim().length > 0)

  const build = async () => {
    if (!hasContent) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const thoughts = sections.find(s => s.id === 'thoughts')?.content ?? ''
      const goals    = sections.find(s => s.id === 'goals')?.content ?? ''
      const notes    = sections.find(s => s.id === 'notes')?.content ?? ''
      const custom   = sections
        .filter(s => !['thoughts', 'goals', 'notes'].includes(s.id))
        .map(s => ({ title: s.title, content: s.content }))

      const res = await api.buildPrompt({ thoughts, goals, notes, custom_sections: custom })
      setResult(res)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Request failed')
    } finally {
      setLoading(false)
    }
  }

  const reset = () => {
    setSections(DEFAULT_SECTIONS.map(s => ({ ...s, content: '' })))
    setResult(null)
    setError(null)
  }

  const fixed = (id: string) => ['thoughts', 'goals', 'notes'].includes(id)

  return (
    <Panel title="Prompt Builder" className="pb">
      {(result || error) && (
        <div className="pb__bar">
          <Button variant="link" onClick={reset}>reset</Button>
        </div>
      )}

      <div className="pb__scroll">
        {!result && (
          <div className="pb__sections">
            {sections.map(section => (
              <div key={section.id} className="pb__section">
                <div className="pb__section-head">
                  {fixed(section.id) ? (
                    <span className="pb__label">{section.title}</span>
                  ) : (
                    <input
                      className="pb__title-input"
                      aria-label="Section title"
                      value={section.title}
                      onChange={e => updateTitle(section.id, e.target.value)}
                    />
                  )}
                  {!fixed(section.id) && (
                    <IconButton label="Remove section" onClick={() => removeSection(section.id)}>
                      <svg viewBox="0 0 12 12" width="12" height="12" fill="none" aria-hidden>
                        <path d="M2 2L10 10M10 2L2 10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                      </svg>
                    </IconButton>
                  )}
                </div>
                <TextField
                  value={section.content}
                  onChange={v => updateSection(section.id, v)}
                  rows={3}
                  placeholder={`${section.title.toLowerCase()}…`}
                />
              </div>
            ))}

            <Button variant="link" onClick={addSection}>+ add section</Button>
          </div>
        )}

        {result && (
          <div className="pb__sections">
            <Card className="pb__card">
              <div className="pb__label">Recommended Model</div>
              <div className="pb__model">
                <Tag tone={MODEL_TONES[result.recommended_model] ?? 'plain'}>
                  {MODEL_LABELS[result.recommended_model] ?? result.recommended_model}
                </Tag>
              </div>
              <div className="pb__reasoning">{result.reasoning}</div>
            </Card>

            <Card className="pb__card">
              <div className="pb__section-head">
                <span className="pb__label">Prompt</span>
                <CopyButton text={result.prompt} label="copy" />
              </div>
              <pre className="pb__prompt">{result.prompt}</pre>
            </Card>
          </div>
        )}

        {error && <Banner tone="error">{error}</Banner>}
      </div>

      {!result && (
        <div className="pb__build">
          <Button variant="primary" onClick={build} disabled={!hasContent || loading}>
            {loading ? (<><Spinner /> Building…</>) : 'Build Prompt'}
          </Button>
        </div>
      )}
    </Panel>
  )
}
