'use client'

import { useState, type KeyboardEvent, type ReactNode } from 'react'
import { Tabs as Root, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

export interface TabItem {
  id: string
  label: string
  /** Shown after the label, e.g. how many moments are in the tab. */
  count?: number
  content: ReactNode
}

/** Accessible tabs on shadcn/Radix: arrow keys move between them, Home and End jump to the ends.
 * `level` picks the larger (page) or smaller (inside a tab) look. */
export function Tabs({ tabs, label, level = 'page' }: { tabs: TabItem[]; label: string; level?: 'page' | 'inner' }) {
  const [selected, setSelected] = useState(tabs[0]?.id)
  if (tabs.length === 0) return null

  // Arrow keys move and select at once, Home and End jump to the ends (Radix would do this a
  // frame later; doing it here keeps selection and focus in step).
  function onKeyDown(event: KeyboardEvent, index: number) {
    const last = tabs.length - 1
    const target =
      event.key === 'ArrowRight' ? (index === last ? 0 : index + 1)
      : event.key === 'ArrowLeft' ? (index === 0 ? last : index - 1)
      : event.key === 'Home' ? 0
      : event.key === 'End' ? last
      : null
    if (target === null) return
    event.preventDefault()
    setSelected(tabs[target].id)
    const list = (event.currentTarget as HTMLElement).parentElement
    list?.querySelectorAll<HTMLElement>('[role="tab"]')[target]?.focus()
  }

  // Radix selects on pointer-down; a plain click (or a synthetic one) selects too.
  return (
    <Root value={tabs.some((t) => t.id === selected) ? selected : tabs[0].id} onValueChange={setSelected}>
      <TabsList level={level} aria-label={label}>
        {tabs.map((tab, index) => (
          <TabsTrigger
            key={tab.id}
            value={tab.id}
            onClick={() => setSelected(tab.id)}
            onKeyDown={(e) => onKeyDown(e, index)}
          >
            {tab.label}
            {tab.count !== undefined && <span className="tab-count ml-1 tabular-nums opacity-80"> ({tab.count})</span>}
          </TabsTrigger>
        ))}
      </TabsList>
      {tabs.map((tab) => (
        <TabsContent key={tab.id} value={tab.id} className={level === 'inner' ? 'pt-5' : undefined}>
          {tab.content}
        </TabsContent>
      ))}
    </Root>
  )
}
