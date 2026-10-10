import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { PIPELINE_STAGES, type JobState } from '../api/types'
import { LanguagePicker } from '../components/LanguagePicker'
import { ErrorNote, PageHeader } from '../components/PageHeader'

const POLL_MS = 1500
const STAGE_WORD = { pending: 'Waiting', running: 'Working', done: 'Done', skipped: 'Already done', failed: 'Stopped' }

export function ProcessPage() {
  const { titleId = '' } = useParams()
  const location = useLocation()
  const autostart = (location.state as { autostart?: string[] } | null)?.autostart

  const [languages, setLanguages] = useState<string[]>(autostart ?? ['en'])
  const [job, setJob] = useState<JobState | null>(null)
  const [error, setError] = useState<string | null>(null)
  const started = useRef(false)

  async function start(chosen: string[]) {
    setError(null)
    try {
      setJob(await api.process(titleId, chosen))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not start processing.')
    }
  }

  // Coming from "Add a title": start straight away. Otherwise show a job already in progress.
  useEffect(() => {
    if (started.current) return
    started.current = true
    if (autostart) {
      void start(autostart)
    } else {
      api.progress(titleId).then(setJob, () => undefined)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- run once on arrival
  }, [titleId])

  const active = job?.status === 'queued' || job?.status === 'running'
  useEffect(() => {
    if (!active) return
    const timer = window.setInterval(() => {
      api.progress(titleId).then(setJob, (e: unknown) => {
        setError(e instanceof Error ? e.message : 'Lost contact with the server.')
      })
    }, POLL_MS)
    return () => window.clearInterval(timer)
  }, [active, titleId])

  const doneCount = job
    ? PIPELINE_STAGES.filter((s) => ['done', 'skipped'].includes(job.stages[s.id])).length
    : 0
  const percent = Math.round((doneCount / PIPELINE_STAGES.length) * 100)

  return (
    <>
      <PageHeader
        step="Add a title · step 2 of 2"
        title={job?.status === 'done' ? 'All set' : 'The projector is warming up'}
      />
      {error && <ErrorNote message={error} />}

      {!job && (
        <div className="stack">
          <div className="field">
            Subtitle languages
            <LanguagePicker value={languages} onChange={setLanguages} />
          </div>
          <div>
            <button type="button" className="primary" onClick={() => void start(languages)}>
              Start processing
            </button>
          </div>
        </div>
      )}

      {job && (
        <div className="stack">
          <div
            className="progress-bar"
            role="progressbar"
            aria-label="Processing progress"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={percent}
          >
            <div style={{ width: `${percent}%` }} />
          </div>
          <ul className="stage-list">
            {PIPELINE_STAGES.map((stage) => {
              const state = job.stages[stage.id] ?? 'pending'
              return (
                <li key={stage.id} data-state={state}>
                  <span>{stage.label}</span>
                  <span>{STAGE_WORD[state]}</span>
                </li>
              )
            })}
          </ul>

          {job.status === 'failed' && (
            <>
              <ErrorNote message={job.error ?? 'Processing stopped.'} />
              <div className="row-actions">
                <button type="button" className="primary" onClick={() => void start(languages)}>
                  Try again
                </button>
                <span className="meta">Finished steps are kept, so this picks up where it stopped.</span>
              </div>
            </>
          )}
          {job.status === 'done' && (
            <div className="row-actions">
              <Link to={`/titles/${titleId}/review`} className="button primary">
                Review the cuts
              </Link>
              <Link to={`/titles/${titleId}/watch`} className="button secondary">
                Watch now
              </Link>
            </div>
          )}
        </div>
      )}
    </>
  )
}
