'use client'

import { useState } from 'react'
import { ChevronRight } from 'lucide-react'
import type { ReviewFilterItem } from '@/api/types'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
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
  const [open, setOpen] = useState<ReadonlySet<string>>(new Set())
  if (filters.length === 0) return <p className="meta m-0">Nothing found.</p>

  function flip(level: string, isOpen: boolean) {
    const next = new Set(open)
    if (isOpen) next.add(level)
    else next.delete(level)
    setOpen(next)
  }

  return (
    <div className="flex flex-col gap-3">
      {LEVELS.map((level) => {
        const group = filters.filter((f) => f.severity === level)
        if (group.length === 0) return null
        const kept = group.filter((f) => f.kept).length
        const isOpen = open.has(level)
        const name = level[0].toUpperCase() + level.slice(1)
        return (
          <Collapsible asChild key={level} open={isOpen} onOpenChange={(o) => flip(level, o)}>
            <section aria-label={`${level} ${word}`} className="border border-line bg-panel/40">
              <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-2">
                <h3 className="m-0 font-sans text-[16px]">
                  <CollapsibleTrigger className="group flex min-h-11 cursor-pointer items-center gap-2.5 text-ink">
                    <ChevronRight
                      className="size-4 text-brass transition-transform duration-300 group-data-[state=open]:rotate-90"
                      aria-hidden="true"
                    />
                    {name}{' '}
                    <span className="meta tabular-nums">
                      · {group.length}
                      {kept > 0 ? `, ${kept} left in` : ''}
                    </span>
                  </CollapsibleTrigger>
                </h3>
                <KeepAll items={group} label={`${level} ${word}`} onSetKept={onSetKept} />
              </div>
              <CollapsibleContent className="overflow-hidden border-t border-line px-2 pb-2 data-[state=open]:animate-in data-[state=open]:fade-in-0">
                <EventTable filters={group} onToggle={onToggle} />
              </CollapsibleContent>
            </section>
          </Collapsible>
        )
      })}
    </div>
  )
}
