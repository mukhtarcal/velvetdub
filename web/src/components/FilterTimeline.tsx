import type { ReviewFilterItem } from '../api/types'
import { CATEGORY_ORDER, categoryLabel, formatTime } from '../lib/format'

/**
 * Labeled lanes, one per category; each filtered moment is a block sized to its length, in the
 * colour of its category (see `--cat-*` in tokens.css). Moments the viewer chose to keep in are
 * drawn as an outline, so state never depends on colour alone, and every lane is named.
 */
export function FilterTimeline({
  filters,
  duration,
}: {
  filters: ReviewFilterItem[]
  duration: number
}) {
  const lanes = CATEGORY_ORDER.filter((c) => filters.some((f) => f.category === c))
  if (lanes.length === 0) {
    return <p className="meta">Nothing will be filtered.</p>
  }

  return (
    <div className="timeline" role="img" aria-label={`Filter timeline: ${lanes.map(categoryLabel).join(', ')}`}>
      {lanes.map((category) => (
        <div className="lane" key={category} data-category={category}>
          <span className="lane-label">
            <span className="swatch" aria-hidden="true" />
            {categoryLabel(category)}
          </span>
          <div className="lane-track">
            {filters
              .filter((f) => f.category === category)
              .map((f) => (
                <span
                  key={f.id}
                  className="block"
                  data-kept={f.kept}
                  style={{
                    left: `${(f.start / duration) * 100}%`,
                    width: `max(3px, ${((f.end - f.start) / duration) * 100}%)`,
                  }}
                  title={`${categoryLabel(f.category)} ${formatTime(f.start)}–${formatTime(f.end)}${f.kept ? ' (kept in)' : ''}`}
                />
              ))}
          </div>
        </div>
      ))}
      <div className="lane axis">
        <span className="lane-label" />
        <div className="lane-track num">
          <span style={{ left: 0 }}>0:00</span>
          <span style={{ right: 0 }}>{formatTime(duration)}</span>
        </div>
      </div>
    </div>
  )
}
