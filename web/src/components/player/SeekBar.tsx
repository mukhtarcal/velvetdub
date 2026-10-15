import { useMemo } from 'react'
import type { FilterItem } from '@/api/types'
import { categoryLabel, drawWorstLast, formatTime } from '@/lib/format'

/** The seek bar, with every filtered moment marked in the colour of its category. Where moments
 * overlap, the worst one is drawn on top (nudity, then sex scenes, violence, scary scenes). */
export function SeekBar({
  time,
  duration,
  filters,
  onSeek,
}: {
  time: number
  duration: number
  filters: FilterItem[]
  onSeek: (seconds: number) => void
}) {
  const marks = useMemo(() => drawWorstLast(filters), [filters])
  const played = duration > 0 ? Math.min(1, time / duration) : 0
  return (
    <div className="seek" style={{ ['--played' as string]: played }}>
      <div className="seek-played" aria-hidden="true" />
      <div className="seek-marks" aria-hidden="true">
        {duration > 0 &&
          marks.map((f) => (
            <span
              key={f.id}
              data-category={f.category}
              title={`${categoryLabel(f.category)} at ${formatTime(f.start)}`}
              style={{
                left: `${(f.start / duration) * 100}%`,
                width: `max(3px, ${((f.end - f.start) / duration) * 100}%)`,
              }}
            />
          ))}
      </div>
      <input
        type="range"
        aria-label="Seek"
        aria-valuetext={`${formatTime(time)} of ${formatTime(duration)}`}
        min={0}
        max={duration || 1}
        step={0.1}
        value={Math.min(time, duration || 1)}
        onChange={(e) => onSeek(Number(e.target.value))}
      />
    </div>
  )
}
