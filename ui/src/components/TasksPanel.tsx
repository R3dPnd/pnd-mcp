import { useEffect, useRef, useState } from 'react'
import { Button, Checkbox, EmptyState, IconButton, Panel, TextInput } from 'pnd-lib-react'

interface Task {
  id: string
  text: string
  done: boolean
  createdAt: number
}

const STORAGE_KEY = 'dann-tasks'

function loadTasks(): Task[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

function saveTasks(tasks: Task[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(tasks))
}

export function TasksPanel() {
  const [tasks, setTasks] = useState<Task[]>(loadTasks)
  const [newText, setNewText] = useState('')
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editText, setEditText] = useState('')
  const inputRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    saveTasks(tasks)
  }, [tasks])

  const addTask = () => {
    const text = newText.trim()
    if (!text) return
    setTasks(prev => [...prev, { id: crypto.randomUUID(), text, done: false, createdAt: Date.now() }])
    setNewText('')
    inputRef.current?.querySelector('input')?.focus()
  }

  const toggleTask = (id: string) => {
    setTasks(prev => prev.map(t => t.id === id ? { ...t, done: !t.done } : t))
  }

  const deleteTask = (id: string) => {
    setTasks(prev => prev.filter(t => t.id !== id))
  }

  const startEdit = (task: Task) => {
    setEditingId(task.id)
    setEditText(task.text)
  }

  const commitEdit = () => {
    if (!editingId) return
    const text = editText.trim()
    if (text) {
      setTasks(prev => prev.map(t => t.id === editingId ? { ...t, text } : t))
    }
    setEditingId(null)
  }

  const clearDone = () => {
    setTasks(prev => prev.filter(t => !t.done))
  }

  const pending = tasks.filter(t => !t.done)
  const done = tasks.filter(t => t.done)

  return (
    <Panel title="Tasks" className="tasks">
      <div className="tasks__add">
        <div ref={inputRef} className="tasks__input">
        <TextInput
          value={newText}
          onChange={setNewText}
          onKeyDown={e => { if (e.key === 'Enter') addTask() }}
          placeholder="new task…"
        />
        </div>
        <Button onClick={addTask} aria-label="Add task">+</Button>
        {done.length > 0 && (
          <Button variant="link" onClick={clearDone}>clear done</Button>
        )}
      </div>

      <div className="tasks__list">
        {tasks.length === 0 && <EmptyState center>no tasks yet</EmptyState>}

        {pending.map(task => (
          <TaskRow
            key={task.id}
            task={task}
            isEditing={editingId === task.id}
            editText={editText}
            onEditTextChange={setEditText}
            onToggle={() => toggleTask(task.id)}
            onStartEdit={() => startEdit(task)}
            onCommitEdit={commitEdit}
            onDelete={() => deleteTask(task.id)}
          />
        ))}

        {done.length > 0 && (
          <>
            <div className="tasks__done-head">Done</div>
            {done.map(task => (
              <TaskRow
                key={task.id}
                task={task}
                isEditing={editingId === task.id}
                editText={editText}
                onEditTextChange={setEditText}
                onToggle={() => toggleTask(task.id)}
                onStartEdit={() => startEdit(task)}
                onCommitEdit={commitEdit}
                onDelete={() => deleteTask(task.id)}
              />
            ))}
          </>
        )}
      </div>

      <div className="tasks__foot">
        {pending.length} remaining · {done.length} done
      </div>
    </Panel>
  )
}

interface TaskRowProps {
  task: Task
  isEditing: boolean
  editText: string
  onEditTextChange: (v: string) => void
  onToggle: () => void
  onStartEdit: () => void
  onCommitEdit: () => void
  onDelete: () => void
}

function TaskRow({ task, isEditing, editText, onEditTextChange, onToggle, onStartEdit, onCommitEdit, onDelete }: TaskRowProps) {
  return (
    <div className="task-row">
      <Checkbox checked={task.done} onChange={onToggle}>
        <span className="vh">{task.done ? 'Mark not done' : 'Mark done'}: {task.text}</span>
      </Checkbox>

      {isEditing ? (
        <input
          autoFocus
          className="task-row__edit"
          aria-label="Edit task"
          value={editText}
          onChange={e => onEditTextChange(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' || e.key === 'Escape') onCommitEdit() }}
          onBlur={onCommitEdit}
        />
      ) : (
        <span onDoubleClick={onStartEdit} className={`task-row__text${task.done ? ' is-done' : ''}`}>
          {task.text}
        </span>
      )}

      <div className="task-row__actions">
        {!isEditing && (
          <IconButton label="Edit task" onClick={onStartEdit}>
            <svg viewBox="0 0 12 12" width="12" height="12" fill="none" aria-hidden>
              <path d="M2 8.5L8.5 2 10 3.5 3.5 10H2V8.5Z" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </IconButton>
        )}
        <IconButton label="Delete task" onClick={onDelete}>
          <svg viewBox="0 0 12 12" width="12" height="12" fill="none" aria-hidden>
            <path d="M2 2L10 10M10 2L2 10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
        </IconButton>
      </div>
    </div>
  )
}
