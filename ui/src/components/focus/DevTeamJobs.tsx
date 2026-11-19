import { useEffect, useState } from 'react'
import { relTime, StatusBadge } from 'pnd-lib-react'
import { api } from '../../lib/api'
import type { DevTeamJob } from '../../types'

const POLL_MS = 5000

export function DevTeamJobs() {
  const [jobs, setJobs] = useState<DevTeamJob[]>([])

  useEffect(() => {
    let cancelled = false
    const load = () => {
      api.getDevTeamJobs({ limit: 10 })
        .then(r => { if (!cancelled) setJobs(r.jobs) })
        .catch(() => {})
    }
    load()
    const id = setInterval(load, POLL_MS)
    return () => { cancelled = true; clearInterval(id) }
  }, [])

  if (jobs.length === 0) return null

  return (
    <div className="devjobs">
      <span className="devjobs__title">Devteam pipelines</span>
      {jobs.map(job => (
        <div key={job.id} className="devjobs__row">
          <StatusBadge status={job.status} />
          <span className="devjobs__project">{job.project}</span>
          <span className="devjobs__task">{job.task}</span>
          <span className="devjobs__time">{relTime(job.started_at)}</span>
        </div>
      ))}
    </div>
  )
}
