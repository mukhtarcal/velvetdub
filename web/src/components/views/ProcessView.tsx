'use client'

import { useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { AnimatePresence, motion } from 'motion/react'
import { Check, LoaderCircle, Minus, X } from 'lucide-react'
import { api } from '@/api/client'
import { PIPELINE_STAGES, type JobState, type ProcessChoices, type StageProgress, type TitleSummary } from '@/api/types'
import { Proscenium } from '@/components/brand/Proscenium'
import { TitleReveal } from '@/components/brand/TitleReveal'
import { Harbor } from '@/components/brand/Harbor'
import { ErrorNote } from '@/components/PageHeader'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { useAsync } from '@/hooks/useAsync'
import { takeAutostart } from '@/lib/autostart'
import { formatDuration } from '@/lib/format'
import { POLL_MS } from '@/lib/polling'
import { cardStatus, isActive, jobPercent, retryChoices } from '@/lib/titles'
import { cn } from '@/lib/utils'
import { EASE } from '@/lib/motion'

const STAGE_WORD: Record<StageProgress, string> = {
  pending: 'Waiting',
  running: 'Working',
  done: 'Done',
  skipped: 'Already done',
  failed: 'Stopped',
}

function StageIcon({ state }: { state: StageProgress }) {
  if (state === 'done' || state === 'skipped') return <Check className="size-4 text-ink" />
  if (state === 'running') return <LoaderCircle className="size-4 animate-spin text-signal" />
  if (state === 'failed') return <X className="size-4 text-signal" />
  return <Minus className="size-4 text-faint" />
}

/** "The projector is warming up": the title processes behind shut curtains, which open when it
 * is done. `autostart` comes from "Add a title" and starts the job on arrival. */
export function ProcessView({ titleId }: { titleId: string }) {
  const [autostart] = useState(() => takeAutostart(titleId))
  const [job, setJob] = useState<JobState | null>(null)
  const [title, setTitle] = useState<TitleSummary | null>(null)
  const [error, setError] = useState<string | null>(null)
  // The curtains move only if you watch the change happen. A title that is already done when the
  // page opens shows them open straight away.
  const [watched, setWatched] = useState(false)
  const started = useRef(false)

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

  const review = useAsync(() => (done ? api.review(titleId) : Promise.resolve(null)), [done, titleId])
  const found = review.data ? review.data.filters.filter((f) => !f.kept).length : 0

  return (
    <>
      <Proscenium
        open={done}
        animate={watched}
        className="-mt-10 h-[min(78svh,720px)] min-h-[520px] sm:-mt-14"
        backdrop={<Harbor beam warming={!done && !failed} />}
      >
        <span className="marquee-label">{`${title?.name ?? 'Your title'} · step 2 of 2`}</span>
        <h1 aria-live="polite" className="mt-4 max-w-[16ch] text-[40px] leading-[1.08] text-ink sm:text-[64px]">
          <TitleReveal text={done ? 'All set' : 'The projector is warming up'} />
        </h1>
        {job && !done && (
          <motion.span
            key={failed ? 'stopped' : 'working'}
            className={cn('mt-6 font-display text-[64px] leading-none tabular-nums sm:text-[96px]', failed ? 'text-signal' : 'text-ink')}
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.5 }}
          >
            {percent}%
          </motion.span>
        )}
      </Proscenium>

      {error && <ErrorNote message={error} />}

      {job && !done && (
        <div className="flex flex-col gap-6">
          <Progress value={percent} aria-label="Processing progress" />
          <ol className="m-0 grid list-none grid-cols-2 gap-3 p-0 sm:grid-cols-3 lg:grid-cols-6">
            {PIPELINE_STAGES.map((stage, i) => {
              const state = job.stages[stage.id] ?? 'pending'
              return (
                <motion.li
                  key={stage.id}
                  data-state={state}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.1 + i * 0.06, duration: 0.4 }}
                  className={cn(
                    'relative flex min-h-[104px] flex-col justify-between gap-3 border bg-surface-deep p-4 transition-colors duration-500',
                    state === 'running' ? 'border-signal/70' : state === 'failed' ? 'border-signal' : 'border-line',
                  )}
                >
                  <span className="flex items-center justify-between">
                    <span className="marquee-label text-faint">{String(i + 1).padStart(2, '0')}</span>
                    <StageIcon state={state} />
                  </span>
                  <span className={cn('text-[15px] leading-5', state === 'pending' ? 'text-faint' : 'text-ink')}>{stage.label}</span>
                  <span className={cn('text-[13.5px]', state === 'failed' ? 'text-signal' : 'text-muted-foreground')}>
                    {STAGE_WORD[state]}
                  </span>
                </motion.li>
              )
            })}
          </ol>
          {failed ? (
            <>
              <ErrorNote message={job.error ?? 'Processing stopped.'} />
              <div className="flex flex-wrap items-center gap-4">
                <Button variant="primary" onClick={() => void start(autostart ?? retryChoices(title))}>
                  Try again
                </Button>
                <span className="meta">Finished steps are kept, so this picks up where it stopped.</span>
              </div>
            </>
          ) : (
            <p className="meta m-0">
              You can leave this page. The film keeps processing and shows up in your library when it is ready.
            </p>
          )}
        </div>
      )}

      {idle && (
        <div className="flex flex-col items-start gap-4">
          <p className="m-0 text-[18px] leading-[29px]">Nothing is processing for this title right now.</p>
          <Button variant="primary" onClick={() => void start(autostart ?? retryChoices(title))}>
            Try again
          </Button>
        </div>
      )}

      <AnimatePresence>
        {done && (review.data || review.error) && (
          <motion.div
            className="flex flex-col items-start gap-5 border-t-2 border-velvet bg-surface-deep p-6 sm:p-8"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            // after the curtains have opened, when you watched them
            transition={{ delay: watched ? 2.2 : 0, duration: 0.5, ease: EASE }}
          >
            <span className="marquee-label">Before the curtain goes up</span>
            <p className="m-0 max-w-[720px] text-[20px] leading-[31px] text-ink-soft">
              {found === 0
                ? 'We found nothing to skip.'
                : `We found ${found} ${found === 1 ? 'moment' : 'moments'} to skip${
                    review.data && review.data.runtime_removed > 0
                      ? `, ${formatDuration(review.data.runtime_removed)} in all`
                      : ''
                  }. Look them over before you watch. You can keep any of them in.`}
            </p>
            <div className="flex flex-wrap items-center gap-x-5 gap-y-3">
              {found === 0 ? (
                <Button asChild variant="primary">
                  <Link href={`/titles/${titleId}/watch`}>Watch now</Link>
                </Button>
              ) : (
                <>
                  <Button asChild variant="primary">
                    <Link href={`/titles/${titleId}/review`}>Review the cuts</Link>
                  </Button>
                  <Button asChild variant="secondary">
                    <Link href={`/titles/${titleId}/watch`}>Watch now</Link>
                  </Button>
                </>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
