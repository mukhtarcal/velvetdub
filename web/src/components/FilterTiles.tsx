import type { ScanCategory } from '../api/types'
import { FILTERS, filterWords } from '../lib/filters'
import { joinLabels } from '../lib/format'

/** Four toggle tiles, one per picture filter. The state is always written out, never colour only.
 * `available` lists what the scanner can check; the rest are greyed out with a plain note. */
export function FilterTiles({
  value,
  onChange,
  available,
  disabled,
}: {
  value: ScanCategory[]
  onChange: (next: ScanCategory[]) => void
  available: ScanCategory[]
  disabled?: boolean
}) {
  const missing = FILTERS.filter((f) => !available.includes(f.id))

  function toggle(id: ScanCategory) {
    onChange(value.includes(id) ? value.filter((c) => c !== id) : [...value, id])
  }

  return (
    <>
      <div className="filter-tiles" role="group" aria-label="What to skip">
        {FILTERS.map((filter) => {
          const unavailable = !available.includes(filter.id)
          const on = !unavailable && value.includes(filter.id)
          return (
            <button
              key={filter.id}
              type="button"
              className="tile"
              aria-pressed={on}
              disabled={disabled || unavailable}
              onClick={() => toggle(filter.id)}
            >
              <span className="tile-top">
                <span className="tile-box" aria-hidden="true">
                  {on && (
                    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="var(--ink)" strokeWidth="2">
                      <path d="M2.5 7.5l3 3 6-7" />
                    </svg>
                  )}
                </span>
                <span className="tile-name">{filter.label}</span>
              </span>
              <span className="tile-hint">{filter.hint}</span>
              <span className="tile-state">
                {unavailable ? 'Not available' : on ? 'Will be skipped' : 'Plays as is'}
              </span>
            </button>
          )
        })}
      </div>
      {missing.length > 0 && (
        <p className="small" role="note">
          This scanner can’t check for {joinLabels(missing.map((f) => filterWords(f.id)))}.
        </p>
      )}
    </>
  )
}
