import { useId, useState } from 'react'
import type { ReviewFilterItem } from '../api/types'
import { EventTable } from './EventTable'
import { KeepAll } from './KeepAll'

const LEVELS = ['strong', 'moderate', 'mild'] as const

/** Moments grouped by how severe they are, so every moderate word sits together. Each group
 * drops down to show its list, and a whole level (say, mild) can be left in with one click. */
export function SeverityGroups({
  filters,
  word,
  onToggle,
  onSetKept,
}: {
  filters: ReviewFilterItem[]
  /** What these are, in lower case: "swearing". */
  word: string
  onToggle: (f: ReviewFilterItem) => void
  onSetKept: (ids: string[], keep: boolean) => void
}) {
  const base = useId()
  const [open, setOpen] = useState<ReadonlySet<string>>(new Set())
  if (filters.length === 0) return <p className="meta">Nothing found.</p>

  function flip(level: string) {
    const next = new Set(open)
    if (!next.delete(level)) next.add(level)
    setOpen(next)
  }

  return (
    <div className="stack" style={{ gap: 12 }}>
      {LEVELS.map((level) => {
        const group = filters.filter((f) => f.severity === level)
        if (group.length === 0) return null
        const kept = group.filter((f) => f.kept).length
        const isOpen = open.has(level)
        const name = level[0].toUpperCase() + level.slice(1)
        return (
          <section key={level} className="severity-group" aria-label={`${level} ${word}`}>
            <div className="group-head">
              <h3>
                <button
                  type="button"
                  className="group-toggle"
                  aria-expanded={isOpen}
                  aria-controls={`${base}-${level}`}
                  onClick={() => flip(level)}
                >
                  <span className="chevron" aria-hidden="true" />
                  {name}{' '}
                  <span className="meta num">
                    · {group.length}
                    {kept > 0 ? `, ${kept} left in` : ''}
                  </span>
                </button>
              </h3>
              <KeepAll items={group} label={`${level} ${word}`} onSetKept={onSetKept} />
            </div>
            <div id={`${base}-${level}`} hidden={!isOpen}>
              {isOpen && <EventTable filters={group} onToggle={onToggle} />}
            </div>
          </section>
        )
      })}
    </div>
  )
}
