'use client'

import { useEffect, useRef, useState, type DragEvent, type FormEvent } from 'react'
import { useRouter } from 'next/navigation'
import { AnimatePresence, motion } from 'motion/react'
import { Film, Upload } from 'lucide-react'
import { api, uploadTitle } from '@/api/client'
import type { ScanCategory } from '@/api/types'
import { FilterTiles } from '@/components/FilterTiles'
import { LanguagePicker } from '@/components/LanguagePicker'
import { Proscenium } from '@/components/brand/Proscenium'
import { TitleReveal } from '@/components/brand/TitleReveal'
import { ErrorNote, SectionHead } from '@/components/PageHeader'
import { Panel } from '@/components/review/Panel'
import { Button, buttonVariants } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Progress } from '@/components/ui/progress'
import { needsLanguage, processChoices, skipSummary, submitState, subtitleSummary } from '@/lib/addTitle'
import { saveAutostart } from '@/lib/autostart'
import { FILTERS } from '@/lib/filters'
import { formatBytes, formatTime } from '@/lib/format'
import { readRuntime } from '@/lib/media'
import { cn } from '@/lib/utils'
import { EASE } from '@/lib/motion'

const ACCEPTED = '.mp4,.m4v,.mov,.mkv,.webm,.avi,video/*'
const ALL_FILTER_IDS = FILTERS.map((f) => f.id)

function nameFromFile(file: File): string {
  return file.name.replace(/\.[^.]+$/, '').replace(/[._]+/g, ' ').trim()
}

export default function AddTitlePage() {
  const router = useRouter()
  const abort = useRef<AbortController | null>(null)
  const formRef = useRef<HTMLFormElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [runtime, setRuntime] = useState<number | null>(null)
  const [name, setName] = useState('')
  const [filters, setFilters] = useState<ScanCategory[]>([])
  const [subtitlesOn, setSubtitlesOn] = useState(false)
  const [languages, setLanguages] = useState<string[]>([])
  const [available, setAvailable] = useState<ScanCategory[]>(ALL_FILTER_IDS)
  const [progress, setProgress] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [dragging, setDragging] = useState(false)

  const uploading = progress !== null

  // Ask which filters the scanner can check. If the server can't say, offer all of them and let
  // the server refuse with a plain message.
  useEffect(() => {
    api.capabilities().then(
      (c) => {
        setAvailable(c.scan_categories)
        setFilters((chosen) => chosen.filter((id) => c.scan_categories.includes(id)))
      },
      () => undefined,
    )
  }, [])

  function choose(chosen: File | null) {
    setFile(chosen)
    setRuntime(null)
    setError(null)
    if (chosen && !name) setName(nameFromFile(chosen))
    if (chosen) {
      void readRuntime(chosen).then(setRuntime)
      // The film is chosen on the stage; the rest of the choices are below it.
      window.setTimeout(() => formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 250)
    }
  }

  function onDrop(event: DragEvent) {
    event.preventDefault()
    setDragging(false)
    if (uploading) return
    const dropped = event.dataTransfer.files?.[0]
    if (dropped) choose(dropped)
  }

  const form = { hasFile: !!file, name, filters, subtitlesOn, languages }
  const { canSubmit, hint } = submitState(form)
  const percent = Math.round((progress ?? 0) * 100)

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!file || !canSubmit) return
    setError(null)
    setProgress(0)
    abort.current = new AbortController()
    try {
      const title = await uploadTitle(file, name.trim(), setProgress, abort.current.signal)
      saveAutostart(title.id, processChoices(form))
      router.push(`/titles/${title.id}/process`)
    } catch (e) {
      setProgress(null)
      setError(e instanceof Error ? e.message : 'The upload failed.')
    }
  }

  return (
    <>
      <Proscenium openOnArrival seats className="-mt-10 h-[min(92svh,860px)] min-h-[600px] sm:-mt-14">
        <motion.span
          className="marquee-label"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1.2, duration: 0.8 }}
        >
          Now showing in your living room
        </motion.span>
        <h1 className="mt-5 max-w-[18ch] text-[38px] leading-[1.06] text-ink sm:text-[56px] lg:text-[72px]">
          <TitleReveal text="Watch it in Spanish. Skip the parts you’d rather not." delay={1.3} />
        </h1>
        <motion.label
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 2.3, duration: 0.6, ease: EASE }}
          onDragOver={(e) => {
            e.preventDefault()
            if (!uploading) setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={cn(
            'group mt-8 flex w-full max-w-[560px] cursor-pointer flex-col items-center gap-3 border border-dashed bg-stage-black/80 px-5 py-5 sm:mt-10 sm:gap-4 sm:px-6 sm:py-7 transition-[border-color,background-color,transform] duration-300 hover:-translate-y-0.5',
            dragging ? 'scale-[1.02] border-brass bg-[#1b1110]' : 'border-brass/45 hover:border-brass',
            uploading && 'pointer-events-none',
          )}
        >
          <span
            aria-hidden="true"
            className={cn(
              'grid size-14 place-items-center border transition-colors duration-300',
              file ? 'border-velvet bg-velvet text-ink' : 'border-brass/50 text-brass group-hover:border-brass',
            )}
          >
            {file ? <Film className="size-6" /> : <Upload className="size-6" />}
          </span>
          <AnimatePresence mode="wait" initial={false}>
            <motion.span
              key={file?.name ?? 'empty'}
              className="flex max-w-full flex-col items-center gap-1"
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.2 }}
            >
              {file ? (
                <>
                  <span className="max-w-full truncate text-[17px] text-ink">{file.name}</span>
                  <span className="meta">
                    {formatBytes(file.size)}
                    {runtime ? ` · ${formatTime(runtime)}` : ''}
                  </span>
                </>
              ) : (
                <>
                  <span className="text-[17px] text-ink">{dragging ? 'Drop the film here' : 'Drop a film here'}</span>
                  <span className="meta">or choose one from your computer. MP4, MOV, MKV, WebM or AVI.</span>
                </>
              )}
            </motion.span>
          </AnimatePresence>
          <span className={cn(buttonVariants({ variant: 'secondary' }), 'group-hover:border-brass/70')}>
            {file ? 'Choose a different file' : 'Choose a file'}
          </span>
          <input
            type="file"
            accept={ACCEPTED}
            hidden
            disabled={uploading}
            onChange={(e) => choose(e.target.files?.[0] ?? null)}
          />
        </motion.label>
      </Proscenium>

      <form ref={formRef} className="grid scroll-mt-28 gap-10 lg:grid-cols-[minmax(0,1fr)_340px] lg:gap-12" onSubmit={submit}>
        <div className="flex min-w-0 flex-col gap-12">
          <section className="flex flex-col gap-5" aria-labelledby="film-h">
            <span className="marquee-label">Add a title · step 1 of 2</span>
            <SectionHead id="film-h" title="The film" />
            <label className="flex max-w-xl flex-col gap-2 text-[14.5px] text-muted-foreground">
              Name
              <Input
                type="text"
                value={name}
                maxLength={200}
                disabled={uploading}
                placeholder={file ? undefined : 'Choose a film above first'}
                onChange={(e) => setName(e.target.value)}
              />
            </label>
          </section>

          <Panel id="filters-h" title="Filters" note="Optional">
            <p className="m-0 max-w-[640px]">
              Choose what to skip. We scan the picture for these and show you every cut before you watch. You can
              keep any of them in.
            </p>
            <FilterTiles value={filters} onChange={setFilters} available={available} disabled={uploading} />
            <p className="meta m-0">
              Swearing in the dialogue is found from the words themselves, so it needs no scan. Once the video is done
              processing you can remove whatever swearing you choose.
            </p>
          </Panel>

          <section className="flex flex-col gap-5" aria-labelledby="subs-h">
            <SectionHead id="subs-h" title="Subtitles" note="Optional" />
            <div className="flex w-fit gap-0 border border-border-control bg-panel p-1" role="radiogroup" aria-label="Subtitles">
              {[
                { on: false, label: 'No subtitles' },
                { on: true, label: 'Add subtitles' },
              ].map((option) => (
                <button
                  key={option.label}
                  type="button"
                  role="radio"
                  aria-checked={subtitlesOn === option.on}
                  disabled={uploading}
                  onClick={() => setSubtitlesOn(option.on)}
                  className="relative min-h-11 cursor-pointer px-5 text-[15px] text-ink-soft transition-colors aria-checked:text-ink"
                >
                  {subtitlesOn === option.on && (
                    <motion.span
                      layoutId="subtitle-choice"
                      className="absolute inset-0 bg-velvet"
                      transition={{ type: 'spring', stiffness: 500, damping: 40 }}
                    />
                  )}
                  <span className="relative">{option.label}</span>
                </button>
              ))}
            </div>
            <AnimatePresence initial={false}>
              {subtitlesOn && (
                <motion.div
                  className="flex flex-col gap-3 overflow-hidden"
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.3, ease: EASE }}
                >
                  <div className="meta">Languages</div>
                  <LanguagePicker value={languages} onChange={setLanguages} disabled={uploading} />
                  {needsLanguage(form) && (
                    <div className="text-[14.5px] text-ink-soft">Choose at least one language, or pick No subtitles.</div>
                  )}
                </motion.div>
              )}
            </AnimatePresence>
          </section>
        </div>

        {/* Your showing: what will happen, and the one button. Sticks beside the form on wide screens. */}
        <aside className="h-fit lg:sticky lg:top-28">
          <div className="flex flex-col gap-6 border border-line border-t-2 border-t-velvet bg-surface-deep p-6">
            <div className="flex flex-col gap-1">
              <span className="marquee-label">Your showing</span>
              <span className="truncate font-display text-[29px] leading-9 text-ink">{name.trim() || 'Untitled'}</span>
            </div>
            <dl className="m-0 flex flex-col gap-4 border-y border-line py-5">
              <div className="flex flex-col gap-1">
                <dt className="meta">Skip</dt>
                <dd className="m-0 text-ink">{skipSummary(filters)}</dd>
              </div>
              <div className="flex flex-col gap-1">
                <dt className="meta">Subtitles</dt>
                <dd className="m-0 text-ink">{subtitleSummary(form)}</dd>
              </div>
            </dl>
            {error && <ErrorNote message={error} />}
            {uploading ? (
              <div className="flex flex-col gap-3">
                <Progress value={percent} aria-label="Upload progress" />
                <div className="flex flex-wrap items-center justify-between gap-4">
                  <span className="meta">Uploading… {percent}%</span>
                  <Button variant="secondary" onClick={() => abort.current?.abort()}>
                    Cancel
                  </Button>
                </div>
              </div>
            ) : (
              <div className="flex flex-col gap-3">
                <Button type="submit" variant="primary" disabled={!canSubmit} className="w-full">
                  Upload and continue
                </Button>
                <span className="meta">{hint}</span>
              </div>
            )}
          </div>
        </aside>
      </form>
    </>
  )
}
