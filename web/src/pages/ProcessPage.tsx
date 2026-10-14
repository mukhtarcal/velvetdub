import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { PIPELINE_STAGES, type JobState, type ProcessChoices, type TitleSummary } from '../api/types'
import { Harbor } from '../components/Harbor'
import { Stage } from '../components/Curtains'
import { ErrorNote, PageHeader } from '../components/PageHeader'
import { useAsync } from '../hooks/useAsync'
import { formatDuration } from '../lib/format'
import { cardStatus, isActive, jobPercent } from '../lib/titles'

export const POLL_MS = 1500
const STAGE_WORD = { pending: 'Waiting', running: 'Working', done: 'Done', skipped: 'Already done', failed: 'Stopped' }

export function ProcessPage() {
  const { titleId = '' } = useParams()
  const location = useLocation()
  const autostart = (location.state as { autostart?: ProcessChoices } | null)?.autostart

  const [job, setJob] = useState<JobState | null>(null)
  const [title, setTitle] = useState<TitleSummary | null>(null)
  const [error, setError] = useState<string | null>(null)
  // The curtains move only if you watch the change happen. A title that is already done when the
  // page opens shows them open straight away.
  const [watched, setWatched] = useState(false)
  const started = useRef(false)

  function choicesToRetry(): ProcessChoices {
    return (
      autostart ?? {
        subtitle_languages: title?.choices?.subtitle_languages ?? [],
        filter_categories: (title?.choices?.filter_categories ?? []) as ProcessChoices['filter_categories'],
      }
    )
  }

  async function start(chosen: ProcessChoices) {
    setError(null)
    try {
      setJob(await api.process(titleId, chosen))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not start processing.')
    }
  }

  const loadTitle = () => api.titleSummary(titleId).then(setTitle, () => undefined)

  // Coming from "Add a title": start straight away. Otherwise show a job already in progress.
  useEffect(() => {
    if (started.current) return
    started.current = true
    void loadTitle()
    if (autostart) {
      void start(autostart)
    } else {
      api.progress(titleId).then(setJob, () => undefined)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- run once on arrival
  }, [titleId])

  const active = isActive(job)
  useEffect(() => {
    if (!active) return
    setWatched(true)
    const timer = window.setInterval(() => {
      api.progress(titleId).then(setJob, (e: unknown) => {
        setError(e instanceof Error ? e.message : 'Lost contact with the server.')
      })
    }, POLL_MS)
    return () => window.clearInterval(timer)
  }, [active, titleId])

  // Once it finishes, fetch the title again for its name and what was scanned.
  useEffect(() => {
    if (job?.status === 'done') void loadTitle()
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only when the job's status changes
  }, [job?.status])

  const alreadyDone = !job && !!title && cardStatus(title, null).kind === 'ready'
  const done = job?.status === 'done' || alreadyDone
  const failed = job?.status === 'failed'
  const idle = !job && !!title && !alreadyDone && !autostart
  const percent = job ? jobPercent(job) : 0

  const review = useAsync(
    () => (done ? api.review(titleId) : Promise.resolve(null)),
    [done, titleId],
  )
  const found = review.data ? review.data.filters.filter((f) => !f.kept).length : 0

  return (
    <>
      <PageHeader
        step={`${title?.name ?? 'Your title'} · step 2 of 2`}
        title={done ? 'All set' : 'The projector is warming up'}
        live
      />
      {error && <ErrorNote message={error} />}

      <Stage open={done} animate={watched}>
        <Harbor beam />
      </Stage>

      {job && !done && (
        <div className="stack" style={{ gap: 16 }}>
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
                  <span className="label">{stage.label}</span>
                  <span className="word">{STAGE_WORD[state]}</span>
                </li>
              )
            })}
          </ul>
          {failed ? (
            <>
              <ErrorNote message={job.error ?? 'Processing stopped.'} />
              <div className="row-actions">
                <button type="button" className="primary" onClick={() => void start(choicesToRetry())}>
                  Try again
                </button>
                <span className="meta">Finished steps are kept, so this picks up where it stopped.</span>
              </div>
            </>
          ) : (
            <p className="processing-note">
              You can leave this page. The film keeps processing and shows up in your library when it is ready.
            </p>
          )}
        </div>
      )}

      {idle && (
        <div className="stack">
          <p className="lead">Nothing is processing for this title right now.</p>
          <div>
            <button type="button" className="primary" onClick={() => void start(choicesToRetry())}>
              Try again
            </button>
          </div>
        </div>
      )}

      {done && (review.data || review.error) && (
        <div className="stack" style={{ gap: 20 }}>
          <p className="lead">
            {found === 0
              ? 'We found nothing to skip.'
              : `We found ${found} ${found === 1 ? 'moment' : 'moments'} to skip${
                  review.data && review.data.runtime_removed > 0
                    ? `, ${formatDuration(review.data.runtime_removed)} in all`
                    : ''
                }. Look them over before you watch. You can keep any of them in.`}
          </p>
          <div className="row-actions" style={{ gap: '12px 20px' }}>
            {found === 0 ? (
              <Link to={`/titles/${titleId}/watch`} className="button primary" style={{ minHeight: 48 }}>
                Watch now
              </Link>
            ) : (
              <>
                <Link to={`/titles/${titleId}/review`} className="button primary" style={{ minHeight: 48 }}>
                  Review the cuts
                </Link>
                <Link to={`/titles/${titleId}/watch`} className="button secondary" style={{ minHeight: 48 }}>
                  Watch now
                </Link>
              </>
            )}
          </div>
        </div>
      )}
    </>
  )
}
