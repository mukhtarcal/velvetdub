import type { ReactNode } from 'react'
import type { ReviewFilterItem, ReviewInfo } from '../api/types'
import { EventTable } from './EventTable'
import { FilterTimeline } from './FilterTimeline'
import { KeepAll } from './KeepAll'
import { SeverityGroups } from './SeverityGroups'
import { Tabs, type TabItem } from './Tabs'
import { FILTERS, filterWords } from '../lib/filters'
import { categoryLabel, formatTime } from '../lib/format'

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

/**
 * Everything cut from a title: an overview timeline, then tabs for scene filtering and swearing,
 * each with "Keep it in" for single moments and whole groups. `extraTabs` adds more (the review
 * page adds translation). `summary` replaces the default line under the overview heading.
 */
export function CutsReview({
  info,
  onToggle,
  onSetKept,
  extraTabs = [],
  summary,
}: {
  info: ReviewInfo
  onToggle: (f: ReviewFilterItem) => void
  onSetKept: SetKept
  extraTabs?: TabItem[]
  summary?: ReactNode
}) {
  const filters = info.filters
  const active = filters.filter((f) => !f.kept)
  const skips = active.filter((f) => f.action === 'skip').length
  const mutes = active.filter((f) => f.action === 'mute' || f.action === 'replace').length
  const scanned = info.scanned_categories
  const duration = info.duration
  const count = (categories: string[]) => filters.filter((f) => categories.includes(f.category)).length
  const sceneIds: string[] = FILTERS.map((f) => f.id)

  return (
    <>
      <section className="panel" aria-labelledby="overview-heading">
        <h2 id="overview-heading" className="signal-heading">
          Overview
        </h2>
        {summary ?? (
          <p className="num">
            {info.runtime_removed > 0 ? `Removes ${formatTime(info.runtime_removed)}` : 'Removes nothing'}
            {info.duration ? ` of ${formatTime(info.duration)}` : ''} · {skips} {skips === 1 ? 'scene' : 'scenes'}{' '}
            skipped · {mutes} {mutes === 1 ? 'word' : 'words'} muted
          </p>
        )}
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
                        onToggle={onToggle}
                        onSetKept={onSetKept}
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
                        onToggle={onToggle}
                        onSetKept={onSetKept}
                      />
                    ),
                  }))}
                />
              </section>
            ),
          },
          ...extraTabs,
        ]}
      />
    </>
  )
}
