import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import type { JobState, ProcessChoices, TitleSummary } from '../api/types'
import { PosterCurtains } from '../components/Curtains'
import { Poster } from '../components/Poster'
import { ErrorNote, PageHeader } from '../components/PageHeader'
import { useAsync } from '../hooks/useAsync'
import { formatTime } from '../lib/format'
import { cardStatus, choicesLine, isActive } from '../lib/titles'
import { POLL_MS } from './ProcessPage'

type Jobs = Record<string, JobState | null>

/** Live job state for every title that is not finished. Polls only while one is processing. */
function useJobs(titles: TitleSummary[] | null, reload: () => void) {
  const [jobs, setJobs] = useState<Jobs>({})

  async function refresh(list: TitleSummary[]) {
    const unfinished = list.filter((t) => cardStatus(t, null).kind !== 'ready')
    const entries = await Promise.all(
      unfinished.map(async (t) => [t.id, await api.progress(t.id).catch(() => null)] as const),
    )
    const next: Jobs = Object.fromEntries(entries)
    setJobs(next)
    // A job that finished while we watched: fetch the list again for its new state.
    return Object.values(next).some((j) => j?.status === 'done')
  }

  const anyActive = Object.values(jobs).some(isActive)

  useEffect(() => {
    if (titles) void refresh(titles).then((finished) => finished && reload())
    // eslint-disable-next-line react-hooks/exhaustive-deps -- refresh when the list changes
  }, [titles])

  useEffect(() => {
    if (!anyActive || !titles) return
    const timer = window.setInterval(() => {
      void refresh(titles).then((finished) => finished && reload())
    }, POLL_MS)
    return () => window.clearInterval(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps -- poll only while something is processing
  }, [anyActive, titles])

  return { jobs, setJobs }
}

export function LibraryPage() {
  const { data: titles, error, loading, reload } = useAsync(() => api.listTitles(), [])
  const { jobs, setJobs } = useJobs(titles, reload)
  const [problem, setProblem] = useState<string | null>(null)

  async function retry(title: TitleSummary) {
    setProblem(null)
    const choices: ProcessChoices = {
      subtitle_languages: title.choices?.subtitle_languages ?? [],
      filter_categories: (title.choices?.filter_categories ?? []) as ProcessChoices['filter_categories'],
    }
    try {
      const job = await api.process(title.id, choices)
      setJobs((all) => ({ ...all, [title.id]: job }))
    } catch (e) {
      setProblem(e instanceof Error ? e.message : 'Could not start processing.')
    }
  }

  return (
    <>
      <PageHeader
        step="Now showing in your living room"
        title="Library"
        action={
          <Link to="/" className="button primary" style={{ minHeight: 48, padding: '0 28px' }}>
            Add a title
          </Link>
        }
      />

      {error && (
        <ErrorNote message="The server isn’t running. Start it with “uv run vd serve”, then reload." />
      )}
      {problem && <ErrorNote message={problem} />}
      {loading && !error && <p className="meta">Loading your titles…</p>}
      {titles?.length === 0 && <p>No titles yet. Add a title to get started.</p>}

      <ul className="title-grid">
        {titles?.map((title, index) => {
          const status = cardStatus(title, jobs[title.id])
          return (
            <li key={title.id} className="title-card">
              <div className="poster">
                <Poster titleId={title.id} fallbackMoon={40 + ((index * 50) % 140)} />
                {status.kind === 'working' && <PosterCurtains />}
              </div>
              <div className="info">
                <div className="name">{title.name}</div>
                {title.duration ? <div className="meta num">{formatTime(title.duration)}</div> : null}
                <div className="meta">{choicesLine(title.choices)}</div>
              </div>

              {status.kind === 'ready' && (
                <div className="row-actions" style={{ gap: '8px 20px' }}>
                  <Link to={`/titles/${title.id}/watch`} className="button secondary">
                    Watch
                  </Link>
                  <Link to={`/titles/${title.id}/review`} className="text">
                    Review the cuts
                  </Link>
                  <Link to={`/titles/${title.id}/download`} className="text">
                    Download
                  </Link>
                </div>
              )}

              {status.kind === 'working' && (
                <div className="stack" style={{ gap: 8 }}>
                  <div
                    className="progress-bar"
                    role="progressbar"
                    aria-label="Processing progress"
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-valuenow={status.percent}
                  >
                    <div style={{ width: `${status.percent}%` }} />
                  </div>
                  <div className="status-line">
                    <span style={{ color: 'var(--ink-soft)' }}>{status.step}</span>
                    <span className="meta num">{status.percent}%</span>
                  </div>
                </div>
              )}

              {status.kind === 'failed' && (
                <div className="row-actions" style={{ gap: '8px 20px' }}>
                  <span style={{ color: 'var(--ink-soft)', fontSize: 14.5 }}>Stopped while {status.stage}.</span>
                  <button type="button" className="text" onClick={() => void retry(title)}>
                    Try again
                  </button>
                </div>
              )}

              {status.kind === 'idle' && (
                <div className="row-actions" style={{ gap: '8px 20px' }}>
                  <span style={{ color: 'var(--ink-soft)', fontSize: 14.5 }}>Not processed yet.</span>
                  <button type="button" className="text" onClick={() => void retry(title)}>
                    Start processing
                  </button>
                </div>
              )}
            </li>
          )
        })}
      </ul>
    </>
  )
}
