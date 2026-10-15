'use client'

import { AnimatePresence, motion } from 'motion/react'
import type { ScanCategory } from '@/api/types'
import { FILTERS, filterWords } from '@/lib/filters'
import { joinLabels } from '@/lib/format'
import { cn } from '@/lib/utils'

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
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4" role="group" aria-label="What to skip">
        {FILTERS.map((filter) => {
          const unavailable = !available.includes(filter.id)
          const on = !unavailable && value.includes(filter.id)
          const state = unavailable ? 'Not available' : on ? 'Will be skipped' : 'Plays as is'
          return (
            <button
              key={filter.id}
              type="button"
              className={cn(
                'group relative flex min-h-[148px] cursor-pointer flex-col gap-2 overflow-hidden border bg-panel p-4 pt-5 text-left transition-[border-color,background-color,transform] duration-300 hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-45 disabled:hover:translate-y-0',
                on ? 'border-velvet bg-[#211414]' : 'border-border-control hover:border-border-strong',
              )}
              aria-pressed={on}
              disabled={disabled || unavailable}
              onClick={() => toggle(filter.id)}
            >
              {/* velvet top rule grows in when the tile is on */}
              <span
                aria-hidden="true"
                className={cn(
                  'absolute inset-x-0 top-0 h-[3px] origin-left bg-velvet transition-transform duration-500 ease-out',
                  on ? 'scale-x-100' : 'scale-x-0',
                )}
              />
              <span className="flex items-center gap-3">
                <span
                  aria-hidden="true"
                  className={cn(
                    'grid size-5 shrink-0 place-items-center rounded-sm border transition-colors duration-200',
                    on ? 'border-velvet bg-velvet' : 'border-border-control bg-ground',
                  )}
                >
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="var(--ink)" strokeWidth="2">
                    <motion.path
                      d="M2.5 7.5l3 3 6-7"
                      initial={false}
                      animate={{ pathLength: on ? 1 : 0, opacity: on ? 1 : 0 }}
                      transition={{ duration: 0.28, ease: 'easeOut' }}
                    />
                  </svg>
                </span>
                <span className="text-[17px] font-semibold text-ink">{filter.label}</span>
              </span>
              <span className="text-[14.5px] leading-[22px] text-ink-soft">{filter.hint}</span>
              <span className="relative mt-auto h-[22px] overflow-hidden text-[14.5px]">
                <AnimatePresence mode="popLayout" initial={false}>
                  <motion.span
                    key={state}
                    className={cn('absolute inset-0', on ? 'text-ink' : 'text-muted-foreground')}
                    initial={{ y: '100%', opacity: 0 }}
                    animate={{ y: 0, opacity: 1 }}
                    exit={{ y: '-100%', opacity: 0 }}
                    transition={{ duration: 0.25, ease: 'easeOut' }}
                  >
                    {state}
                  </motion.span>
                </AnimatePresence>
              </span>
            </button>
          )
        })}
      </div>
      {missing.length > 0 && (
        <p className="meta m-0" role="note">
          This scanner can’t check for {joinLabels(missing.map((f) => filterWords(f.id)))}.
        </p>
      )}
    </>
  )
}
