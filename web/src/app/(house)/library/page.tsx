'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { motion } from 'motion/react'
import { Play } from 'lucide-react'
import { api } from '@/api/client'
import type { JobState, TitleSummary } from '@/api/types'
import { PosterCurtains } from '@/components/brand/Curtains'
import { Proscenium } from '@/components/brand/Proscenium'
import { Poster } from '@/components/brand/Poster'
import { ErrorNote, PageHeader } from '@/components/PageHeader'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { useAsync } from '@/hooks/useAsync'
import { formatTime } from '@/lib/format'
import { POLL_MS } from '@/lib/polling'
import { cardStatus, choicesLine, isActive, retryChoices } from '@/lib/titles'
import { cn } from '@/lib/utils'
import { EASE } from '@/lib/motion'

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

export default function LibraryPage() {
  const { data: titles, error, loading, reload } = useAsync(() => api.listTitles(), [])
  const { jobs, setJobs } = useJobs(titles, reload)
  const [problem, setProblem] = useState<string | null>(null)

  async function retry(title: TitleSummary) {
    setProblem(null)
    try {
      const job = await api.process(title.id, retryChoices(title))
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
          <Button asChild variant="primary">
            <Link href="/">Add a title</Link>
          </Button>
        }
      />

      {error && <ErrorNote message="The server isn’t running. Start it with “uv run vd serve”, then reload." />}
      {problem && <ErrorNote message={problem} />}
      {loading && !error && <LoadingGrid />}
      {titles?.length === 0 && <EmptyHouse />}

      {titles && titles.length > 0 && (
        <ul className="m-0 grid list-none grid-cols-1 gap-x-6 gap-y-12 p-0 sm:grid-cols-2 lg:grid-cols-3">
          {titles.map((title, index) => {
            const status = cardStatus(title, jobs[title.id])
            const ready = status.kind === 'ready'
            const featured = index === 0
            return (
              <motion.li
                key={title.id}
                className={cn(
                  'group flex flex-col gap-4',
                  featured && 'sm:col-span-2 lg:col-span-3 lg:grid lg:grid-cols-[minmax(0,1.7fr)_minmax(0,1fr)] lg:items-center lg:gap-10',
                )}
                initial={{ opacity: 0, y: 24 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: Math.min(index, 8) * 0.07, ease: EASE }}
              >
                <PosterFrame href={ready ? `/titles/${title.id}/watch` : undefined} label={`Watch ${title.name}`}>
                  <Poster titleId={title.id} fallbackMoon={40 + ((index * 50) % 140)} />
                  {status.kind === 'working' ? <PosterCurtains /> : <span className="poster-drapes absolute inset-0" aria-hidden="true" />}
                  {ready && (
                    <span
                      aria-hidden="true"
                      className="absolute inset-0 z-[3] grid place-items-center opacity-0 transition-opacity duration-300 group-hover:opacity-100"
                    >
                      <span className={cn('grid place-items-center bg-velvet text-ink', featured ? 'size-20' : 'size-14')}>
                        <Play className={featured ? 'size-8' : 'size-6'} />
                      </span>
                    </span>
                  )}
                </PosterFrame>

                <div className="flex flex-col gap-4">
                  <div className="flex flex-col gap-1.5">
                    {featured && <span className="marquee-label">Most recent</span>}
                    <div
                      className={cn(
                        featured ? 'font-display text-[36px] leading-[42px] sm:text-[45px] sm:leading-[54px]' : 'text-[19px] font-semibold',
                        'text-ink',
                      )}
                    >
                      {title.name}
                    </div>
                    <div className="meta">
                      {title.duration ? `${formatTime(title.duration)} · ` : ''}
                      {choicesLine(title.choices)}
                    </div>
                  </div>

                  {ready && (
                    <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
                      <Button asChild variant="secondary">
                        <Link href={`/titles/${title.id}/watch`}>Watch</Link>
                      </Button>
                      <Link href={`/titles/${title.id}/review`} className="text-action">
                        Review the cuts
                      </Link>
                      <Link href={`/titles/${title.id}/download`} className="text-action">
                        Download
                      </Link>
                    </div>
                  )}

                  {status.kind === 'working' && (
                    <div className="flex flex-col gap-2">
                      <Progress value={status.percent} aria-label="Processing progress" />
                      <div className="flex items-center justify-between gap-3 text-[14.5px]">
                        <span className="text-ink-soft">{status.step}</span>
                        <span className="meta">{status.percent}%</span>
                      </div>
                    </div>
                  )}

                  {(status.kind === 'failed' || status.kind === 'idle') && (
                    <div className="flex flex-wrap items-center gap-x-5 gap-y-1">
                      <span className="text-[14.5px] text-ink-soft">
                        {status.kind === 'failed' ? `Stopped while ${status.stage}.` : 'Not processed yet.'}
                      </span>
                      <Button variant="text" onClick={() => void retry(title)}>
                        {status.kind === 'failed' ? 'Try again' : 'Start processing'}
                      </Button>
                    </div>
                  )}
                </div>
              </motion.li>
            )
          })}
        </ul>
      )}
    </>
  )
}

/** 16:9 frame with a fine brass line, the one place the poster frame colour is used. */
function PosterFrame({ href, label, children }: { href?: string; label: string; children: React.ReactNode }) {
  const frame =
    'relative block aspect-video overflow-hidden border border-brass/40 bg-stage-black transition-colors duration-300 group-hover:border-brass'
  if (!href) return <div className={frame}>{children}</div>
  return (
    <Link href={href} className={frame} aria-label={label}>
      {children}
    </Link>
  )
}

function LoadingGrid() {
  return (
    <ul className="m-0 grid list-none grid-cols-1 gap-6 p-0 sm:grid-cols-2 lg:grid-cols-3" aria-label="Loading your titles">
      {[0, 1, 2].map((i) => (
        <li key={i} className="flex flex-col gap-4">
          <div className="aspect-video animate-pulse border border-line bg-surface-deep" />
          <div className="h-5 w-2/3 animate-pulse bg-panel" />
        </li>
      ))}
    </ul>
  )
}

/** Nothing on the bill yet: the curtains stay shut, with the way in written on them. */
function EmptyHouse() {
  return (
    <Proscenium className="h-[min(64svh,600px)] min-h-[440px]" seats>
      <span className="marquee-label">Tonight’s bill</span>
      <h2 className="mt-4 text-[40px] leading-[1.05] text-ink sm:text-[64px]">No titles yet</h2>
      <p className="mt-4 max-w-[460px] text-on-velvet">
        Add a title to get started. We scan it, show you every cut, and then it plays here.
      </p>
      <Button asChild variant="secondary" className="mt-6 border-on-velvet/60 bg-velvet-shadow/60">
        <Link href="/">Add a title</Link>
      </Button>
    </Proscenium>
  )
}
