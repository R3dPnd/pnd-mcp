import { Suspense, lazy, useState } from 'react'
import { EmptyState, IconButton, Tabs } from 'pnd-lib-react'
import { useDannEvents } from './hooks/useDannEvents'
import { useFocusModeShortcut } from './hooks/useFocusModeShortcut'
import { useDannStore } from './hooks/useDannState'
import { StatusBar } from './components/StatusBar'
import { ModulesPanel } from './components/ModulesPanel'
import { FocusAreasPanel } from './components/FocusAreasPanel'
import LogPanel from './components/LogPanel'
import { LeftNav } from './components/LeftNav'
import { VoicePanel } from './components/VoicePanel'
import { VoiceWidget } from './components/VoiceWidget'
import { TerminalIndicator } from './components/TerminalIndicator'
import { FocusMode } from './components/focus/FocusMode'

// Lazy-load heavy components
const MetricsPage = lazy(() => import('./components/MetricsPage'))
const SystemPanel = lazy(() => import('./components/SystemPanel'))
const NotesPanel = lazy(() => import('./components/NotesPanel').then(m => ({ default: m.NotesPanel })))
const ChatPanel = lazy(() => import('./components/ChatPanel')) // the main "DANN" tab: chat + per-focus-area terminal

// ── Tab types ─────────────────────────────────────────────────────────────────
// Terminals live inside the DANN tab now (one per active work stream's focus
// area, see ChatPanel) — there's no standalone terminal-tab system anymore
// since the two panels that used to open one (Projects, Notes) either no
// longer exist or no longer map onto a focus area.

type Tab = 'dann' | 'focus' | 'modules' | 'notes' | 'metrics' | 'system'

function tabLabel(t: Tab, personaName: string): string {
  if (t === 'dann') return personaName.toUpperCase()
  if (t === 'focus') return 'Focus Areas'
  if (t === 'modules') return 'Modules'
  if (t === 'notes') return 'Notes'
  if (t === 'system') return 'System'
  return 'Metrics'
}

// ── App ───────────────────────────────────────────────────────────────────────

export default function App() {
  useDannEvents()
  useFocusModeShortcut()

  const focusMode = useDannStore(s => s.focusMode)
  const setFocusMode = useDannStore(s => s.setFocusMode)
  const personaName = useDannStore(s => s.persona.name)

  const tabs: Tab[] = ['dann', 'focus', 'modules', 'notes', 'metrics', 'system']
  const [activeTabId, setActiveTabId] = useState<Tab>('dann')

  const tabItems = tabs.map((t) => ({ id: t, label: tabLabel(t, personaName) }))
  const loading = <EmptyState>Loading…</EmptyState>
  const pane = (id: Tab, scroll: boolean) =>
    `app-pane ${scroll ? 'app-pane--scroll' : ''} ${activeTabId === id ? '' : 'is-hidden'}`

  return (
    <>
    <div className={`app ${focusMode ? 'is-focus' : ''}`}>
      <StatusBar />

      {/* Tab bar. The persona tab's focus-mode button sits beside the tabs. */}
      <div className="app-tabs">
        <Tabs tabs={tabItems} active={activeTabId} onChange={setActiveTabId} label="Sections" />
        <IconButton label="Enter Focus Mode (Cmd/Ctrl+Shift+F)" onClick={() => setFocusMode(true)}>
          ⛶
        </IconButton>
      </div>

      {/* Body: left nav + tab content + persistent voice panel */}
      <div className="app-body">
      <LeftNav />

      {/* Tab content — all panels stacked absolutely so display:none never nukes canvas contexts */}
      <main className="app-main">

        {/* Chat with the persona + the live terminal for whichever work stream's focus area is active */}
        <div className={pane('dann', false)}>
          <Suspense fallback={loading}>
            <ChatPanel />
          </Suspense>
        </div>

        <div className={pane('focus', true)}>
          <div className="app-page">
            <FocusAreasPanel />
          </div>
        </div>

        <div className={pane('modules', true)}>
          <div className="app-page">
            <ModulesPanel />
          </div>
        </div>

        <div className={pane('notes', true)}>
          <div className="app-page">
            <Suspense fallback={loading}>
              <NotesPanel />
            </Suspense>
          </div>
        </div>

        <div className={pane('metrics', true)}>
          <Suspense fallback={loading}>
            <MetricsPage />
          </Suspense>
        </div>

        <div className={pane('system', true)}>
          <Suspense fallback={loading}>
            <SystemPanel />
          </Suspense>
        </div>
      </main>

      {/* Permanent voice panel — always visible right sidebar */}
      <VoicePanel />
      </div>

      <VoiceWidget />
      <LogPanel />
      <TerminalIndicator />
    </div>
    <FocusMode active={focusMode} onExit={() => setFocusMode(false)} />
    </>
  )
}
