'use client'

import { useEffect, useRef } from 'react'
import Link from 'next/link'
import { api } from '@/api/client'
import { ErrorNote, PageHeader } from '@/components/PageHeader'
import { CutsReview } from '@/components/review/CutsReview'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { useAsync } from '@/hooks/useAsync'
import { useCuts } from '@/hooks/useCuts'
import { copySummary, downloadControl } from '@/lib/download'

const POLL_MS = 2000

/** Choose what to cut, then download a copy of the film with those cuts made for good. It is the
 * review page's list, with the same "Keep it in" controls, ending in a download. */
export function DownloadView({ titleId }: { titleId: string }) {
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
          <Link href={`/titles/${titleId}/review`} className="text-action inline-flex min-h-11 items-center">
            Back to the review
          </Link>
        }
      >
        <p className="m-0 max-w-[640px]">
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
          summary={state && <p className="m-0 tabular-nums">{copySummary(state)}</p>}
        />
      )}

      {state && control && (
        <div className="sticky bottom-0 z-30 -mx-4 flex flex-col gap-4 border-t-2 border-velvet bg-ground px-4 py-5 sm:-mx-8 sm:px-8">
          {status === 'failed' && state.error && <ErrorNote message={state.error} />}
          {status === 'working' && <Progress value={state.percent} aria-label="Making your copy" />}
          <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
            {control.action === 'save' ? (
              <Button asChild variant="primary">
                <a ref={link} href={api.exportFileUrl(titleId)} download={state.filename}>
                  {control.label}
                </a>
              </Button>
            ) : (
              <Button
                variant="primary"
                disabled={control.action === 'working' || control.action === 'blocked'}
                onClick={() => void start()}
              >
                {control.label}
              </Button>
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
