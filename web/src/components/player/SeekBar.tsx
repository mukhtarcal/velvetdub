import type { FilterItem } from '../../api/types'
import { categoryLabel, formatTime } from '../../lib/format'

/** The seek bar, with every filtered moment marked in signal red. */
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
  return (
    <div className="seek">
      <div className="seek-marks" aria-hidden="true">
        {duration > 0 &&
          filters.map((f) => (
            <span
              key={f.id}
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
