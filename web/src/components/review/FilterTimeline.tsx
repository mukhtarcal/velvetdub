'use client'

import { motion } from 'motion/react'
import type { ReviewFilterItem } from '@/api/types'
import { CATEGORY_ORDER, categoryLabel, formatTime } from '@/lib/format'
import { cn } from '@/lib/utils'
import { EASE } from '@/lib/motion'

/**
 * Labeled lanes, one per category; each filtered moment is a block sized to its length, in the
 * colour of its category (see `--cat-*` in tokens.css). Moments the viewer chose to keep in are
 * drawn as an outline, so state never depends on colour alone, and every lane is named.
 */
export function FilterTimeline({ filters, duration }: { filters: ReviewFilterItem[]; duration: number | null }) {
  if (!duration) {
    return <p className="meta m-0">The film’s length isn’t known yet, so the timeline can’t be drawn.</p>
  }
  const lanes = CATEGORY_ORDER.filter((c) => filters.some((f) => f.category === c))
  if (lanes.length === 0) {
    return <p className="meta m-0">Nothing will be filtered.</p>
  }

  return (
    <div
      className="timeline flex flex-col gap-1.5"
      role="img"
      aria-label={`Filter timeline: ${lanes.map(categoryLabel).join(', ')}`}
    >
      {lanes.map((category, laneIndex) => (
        <div
          className="lane grid grid-cols-[112px_1fr] items-center gap-3 sm:grid-cols-[160px_1fr]"
          key={category}
          data-category={category}
        >
          <span className="flex items-center gap-2 text-[14.5px] text-muted-foreground">
            <span className="swatch size-2.5 shrink-0 bg-[var(--cat)]" aria-hidden="true" />
            <span className="truncate">{categoryLabel(category)}</span>
          </span>
          <motion.div
            className="relative h-6 origin-left border border-line bg-track"
            initial={{ scaleX: 0 }}
            animate={{ scaleX: 1 }}
            transition={{ duration: 0.7, delay: laneIndex * 0.08, ease: EASE }}
          >
            {filters
              .filter((f) => f.category === category)
              .map((f) => (
                <span
                  key={f.id}
                  className={cn(
                    'block absolute inset-y-0 transition-colors duration-300',
                    f.kept ? 'border border-[var(--cat)] bg-transparent' : 'bg-[var(--cat)]',
                  )}
                  data-kept={f.kept}
                  style={{
                    left: `${(f.start / duration) * 100}%`,
                    width: `max(3px, ${((f.end - f.start) / duration) * 100}%)`,
                  }}
                  title={`${categoryLabel(f.category)} ${formatTime(f.start)}–${formatTime(f.end)}${f.kept ? ' (kept in)' : ''}`}
                />
              ))}
          </motion.div>
        </div>
      ))}
      <div className="lane axis grid grid-cols-[112px_1fr] gap-3 sm:grid-cols-[160px_1fr]">
        <span />
        <div className="relative h-5 text-[13px] text-faint tabular-nums">
          <span className="absolute left-0">0:00</span>
          <span className="absolute right-0">{formatTime(duration)}</span>
        </div>
      </div>
    </div>
  )
}
