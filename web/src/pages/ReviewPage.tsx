import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
import type { ReviewFilterItem } from '../api/types'
import { EventTable } from '../components/EventTable'
import { FilterTimeline } from '../components/FilterTimeline'
import { KeepAll } from '../components/KeepAll'
import { ErrorNote, PageHeader } from '../components/PageHeader'
import { ScriptEditor } from '../components/ScriptEditor'
import { SeverityGroups } from '../components/SeverityGroups'
import { Tabs } from '../components/Tabs'
import { useAsync } from '../hooks/useAsync'
import { FILTERS, filterWords } from '../lib/filters'
import { categoryLabel, formatTime } from '../lib/format'
import { languageLabel } from '../lib/titles'

// Spoken-word categories are found from the transcript; everything else comes from the picture.
const WORD_TABS = ['swearing', 'blasphemy']

type SetKept = (ids: string[], keep: boolean) => void

/** One kind of scene on its own: its timeline lane, "Leave all in", then every moment. */
function SceneKindPanel({
  category,
  filters,
  duration,
  notChecked,
  onToggle,
  onSetKept,
}: {
  category: string
  filters: ReviewFilterItem[]
  duration: number | null
  notChecked: boolean
  onToggle: (f: ReviewFilterItem) => void
  onSetKept: SetKept
}) {
  const mine = filters.filter((f) => f.category === category)
  if (notChecked) {
    return (
      <p className="meta">
        Not checked for {filterWords(category)}. Choose it when you add a title to have it scanned.
      </p>
    )
  }
  return (
    <div className="stack">
      {duration ? (
        <FilterTimeline filters={mine} duration={duration} />
      ) : (
        <p className="meta">The film’s length isn’t known yet, so the timeline can’t be drawn.</p>
      )}
      <div className="tab-actions">
        <KeepAll items={mine} label={filterWords(category)} onSetKept={onSetKept} />
      </div>
      {mine.length > 0 && <EventTable filters={mine} onToggle={onToggle} />}
    </div>
  )
}

export function ReviewPage() {
  const { titleId = '' } = useParams()
  const review = useAsync(() => api.review(titleId), [titleId])
  const playback = useAsync(() => api.playback(titleId), [titleId])
  const [error, setError] = useState<string | null>(null)
  const errorRef = useRef<HTMLDivElement>(null)
  // A failed click can be far below the note at the top, so bring it into view.
  useEffect(() => {
    if (error) errorRef.current?.scrollIntoView?.({ block: 'center' })
  }, [error])

  async function setKept(ids: string[], keep: boolean) {
    if (ids.length === 0) return
    setError(null)
    try {
      await api.keepEvents(titleId, ids, keep)
      review.reload()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not update those moments.')
    }
  }

  const toggle = (f: ReviewFilterItem) => void setKept([f.id], !f.kept)

  const info = review.data
  const filters = info?.filters ?? []
  const active = filters.filter((f) => !f.kept)
  const skips = active.filter((f) => f.action === 'skip').length
  const mutes = active.filter((f) => f.action === 'mute' || f.action === 'replace').length
  const scanned = info?.scanned_categories ?? null
  const languages = playback.data?.subtitle_tracks.map((t) => t.language) ?? []
  const count = (categories: string[]) => filters.filter((f) => categories.includes(f.category)).length
  const duration = info?.duration ?? null
  const sceneIds: string[] = FILTERS.map((f) => f.id)

  return (
    <>
      <PageHeader
        step="Before the curtain goes up"
        title={info?.name ?? 'Review the cuts'}
        action={
          <Link to={`/titles/${titleId}/watch`} className="button primary" style={{ minHeight: 48, padding: '0 28px' }}>
            Watch
          </Link>
        }
      />

      {review.error && <ErrorNote message={review.error} />}
      {error && (
        <div ref={errorRef}>
          <ErrorNote message={error} />
        </div>
      )}

      {info && (
        <>
          <section className="panel" aria-labelledby="overview-heading">
            <h2 id="overview-heading" className="signal-heading">
              Overview
            </h2>
            <p className="num">
              {info.runtime_removed > 0 ? `Removes ${formatTime(info.runtime_removed)}` : 'Removes nothing'}
              {info.duration ? ` of ${formatTime(info.duration)}` : ''} · {skips} {skips === 1 ? 'scene' : 'scenes'}{' '}
              skipped · {mutes} {mutes === 1 ? 'word' : 'words'} muted
            </p>
            {duration ? (
              <FilterTimeline filters={filters} duration={duration} />
            ) : (
              <p className="meta">The film’s length isn’t known yet, so the timeline can’t be drawn.</p>
            )}
          </section>

          <Tabs
            label="What to review"
            tabs={[
              {
                id: 'scenes',
                label: 'Scene filtering',
                count: count(sceneIds),
                content: (
                  <section className="panel" aria-labelledby="scenes-heading">
                    <h2 id="scenes-heading" className="signal-heading">
                      Scene filtering
                    </h2>
                    <Tabs
                      level="inner"
                      label="Kind of scene"
                      tabs={FILTERS.map((f) => ({
                        id: f.id,
                        label: f.label,
                        count: count([f.id]),
                        content: (
                          <SceneKindPanel
                            category={f.id}
                            filters={filters}
                            duration={duration}
                            notChecked={scanned !== null && !scanned.includes(f.id)}
                            onToggle={toggle}
                            onSetKept={(ids, keep) => void setKept(ids, keep)}
                          />
                        ),
                      }))}
                    />
                  </section>
                ),
              },
              {
                id: 'swearing',
                label: 'Swearing',
                count: count(WORD_TABS),
                content: (
                  <section className="panel" aria-labelledby="swearing-heading">
                    <h2 id="swearing-heading" className="signal-heading">
                      Swearing
                    </h2>
                    <Tabs
                      level="inner"
                      label="Kind of language"
                      tabs={WORD_TABS.map((c) => ({
                        id: c,
                        label: categoryLabel(c).replace(/^./, (x) => x.toUpperCase()),
                        count: count([c]),
                        content: (
                          <SeverityGroups
                            filters={filters.filter((f) => f.category === c)}
                            word={categoryLabel(c)}
                            onToggle={toggle}
                            onSetKept={(ids, keep) => void setKept(ids, keep)}
                          />
                        ),
                      }))}
                    />
                  </section>
                ),
              },
              {
                id: 'translation',
                label: 'Translation',
                count: languages.length,
                content: (
                  <section className="panel" aria-labelledby="translation-heading">
                    <h2 id="translation-heading">Translation</h2>
                    {languages.length > 0 ? (
                      <Tabs
                        level="inner"
                        label="Language"
                        tabs={languages.map((code) => ({
                          id: code,
                          label: languageLabel(code),
                          content: <ScriptEditor titleId={titleId} language={code} />,
                        }))}
                      />
                    ) : (
                      <p className="meta">No subtitles have been written for this title yet.</p>
                    )}
                  </section>
                ),
              },
            ]}
          />
        </>
      )}
    </>
  )
}
