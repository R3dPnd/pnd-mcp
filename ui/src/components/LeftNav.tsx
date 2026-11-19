import { useState } from 'react'
import { NavRail, NavRailItem } from 'pnd-lib-react'
import { TasksPanel } from './TasksPanel'
import { PromptBuilderPanel } from './PromptBuilderPanel'

type Panel = 'tasks' | 'prompt-builder' | null

export function LeftNav() {
  const [activePanel, setActivePanel] = useState<Panel>(null)

  const toggle = (panel: Panel) => {
    setActivePanel(prev => prev === panel ? null : panel)
  }

  return (
    <div className="left-nav">
      {/* Icon rail */}
      <NavRail>
        <NavRailItem label="Tasks" active={activePanel === 'tasks'} onClick={() => toggle('tasks')}>
          <TasksIcon />
        </NavRailItem>
        <NavRailItem label="Prompt Builder" active={activePanel === 'prompt-builder'} onClick={() => toggle('prompt-builder')}>
          <PromptBuilderIcon />
        </NavRailItem>
      </NavRail>

      {/* Expandable panel */}
      <div className={`left-nav__drawer ${activePanel ? 'is-open' : ''}`}>
        <div className="left-nav__inner">
          {activePanel === 'tasks' && <TasksPanel />}
          {activePanel === 'prompt-builder' && <PromptBuilderPanel />}
        </div>
      </div>
    </div>
  )
}

function TasksIcon() {
  return (
    <svg viewBox="0 0 16 16" className="left-nav__icon" fill="none">
      <rect x="1.5" y="2.5" width="4" height="4" rx="0.5" stroke="currentColor" strokeWidth="1.2"/>
      <path d="M2.5 4.5L3.5 5.5L5.5 3.5" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round" strokeLinejoin="round"/>
      <line x1="8" y1="4.5" x2="14.5" y2="4.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
      <rect x="1.5" y="9.5" width="4" height="4" rx="0.5" stroke="currentColor" strokeWidth="1.2"/>
      <line x1="8" y1="11.5" x2="14.5" y2="11.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
    </svg>
  )
}

function PromptBuilderIcon() {
  return (
    <svg viewBox="0 0 16 16" className="left-nav__icon" fill="none">
      <path d="M8 1L9.2 5.8L14 7L9.2 8.2L8 13L6.8 8.2L2 7L6.8 5.8L8 1Z" stroke="currentColor" strokeWidth="1.1" strokeLinejoin="round"/>
      <path d="M13 11L13.6 13L15 13.6L13.6 14.2L13 16L12.4 14.2L11 13.6L12.4 13L13 11Z" stroke="currentColor" strokeWidth="0.9" strokeLinejoin="round"/>
    </svg>
  )
}
