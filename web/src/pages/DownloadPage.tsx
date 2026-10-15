import { useEffect, useRef } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { CutsReview } from '../components/CutsReview'
import { ErrorNote, PageHeader } from '../components/PageHeader'
import { useAsync } from '../hooks/useAsync'
import { useCuts } from '../hooks/useCuts'
import { copySummary, downloadControl } from '../lib/download'

const POLL_MS = 2000

/** Choose what to cut, then download a copy of the film with those cuts made for good. It is the
 * review page's list, with the same "Keep it in" controls, ending in a download. */
export function DownloadPage() {
  const { titleId = '' } = useParams()
  const exported = useAsync(() => api.exportState(titleId), [titleId])
  const { review, error, errorRef, setKept, toggle } = useCuts(titleId, exported.reload)
  const link = useRef<HTMLAnchorElement>(null)
  // The file is handed over by itself only when you watched it being made, not when you arrive
  // to a copy that was already waiting.
  const sawWorking = useRef(false)

  const state = exported.data
  const status = state?.status

  useEffect(() => {
    if (status !== 'working') return
    sawWorking.current = true
    const timer = window.setInterval(exported.reload, POLL_MS)
    return () => window.clearInterval(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps -- poll only while the copy is being made
  }, [status])

  useEffect(() => {
    if (status === 'ready' && sawWorking.current) {
      sawWorking.current = false
      link.current?.click()
    }
  }, [status])

  async function start() {
    try {
      await api.startExport(titleId)
    } finally {
      exported.reload()
    }
  }

  const info = review.data
  const control = state ? downloadControl(state) : null

  return (
    <>
      <PageHeader
        step={info?.name ?? 'Download'}
        title="Download"
        action={
          <Link to={`/titles/${titleId}/review`} className="text">
            Back to the review
          </Link>
        }
      >
        <p style={{ margin: 0, maxWidth: 640 }}>
          Choose what to cut out of your copy. Everything listed is cut unless you leave it in, and the original
          film is never changed.
        </p>
      </PageHeader>

      {review.error && <ErrorNote message={review.error} />}
      {exported.error && <ErrorNote message={exported.error} />}
      {error && (
        <div ref={errorRef}>
          <ErrorNote message={error} />
        </div>
      )}

      {info && (
        <CutsReview
          info={info}
          onToggle={toggle}
          onSetKept={setKept}
          summary={state && <p className="num">{copySummary(state)}</p>}
        />
      )}

      {state && control && (
        <div className="submit-bar">
          {status === 'failed' && state.error && <ErrorNote message={state.error} />}
          {status === 'working' && (
            <div
              className="progress-bar"
              role="progressbar"
              aria-label="Making your copy"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={state.percent}
            >
              <div style={{ width: `${state.percent}%` }} />
            </div>
          )}
          <div className="row-actions" style={{ gap: '16px 24px' }}>
            {control.action === 'save' ? (
              <a
                ref={link}
                href={api.exportFileUrl(titleId)}
                download={state.filename}
                className="button primary"
                style={{ minHeight: 48, padding: '0 28px' }}
              >
                {control.label}
              </a>
            ) : (
              <button
                type="button"
                className="primary"
                style={{ minHeight: 48, padding: '0 28px' }}
                disabled={control.action === 'working' || control.action === 'blocked'}
                onClick={() => void start()}
              >
                {control.label}
              </button>
            )}
            <span className="meta" aria-live="polite">
              {control.hint}
            </span>
          </div>
        </div>
      )}
    </>
  )
}
