import { useId, useState, type KeyboardEvent, type ReactNode } from 'react'

export interface TabItem {
  id: string
  label: string
  /** Shown after the label, e.g. how many moments are in the tab. */
  count?: number
  content: ReactNode
}

/** Accessible tabs: arrow keys move between them, Home and End jump to the ends. `level` picks
 * the larger (page) or smaller (inside a tab) look. */
export function Tabs({
  tabs,
  label,
  level = 'page',
}: {
  tabs: TabItem[]
  label: string
  level?: 'page' | 'inner'
}) {
  const base = useId()
  const [selected, setSelected] = useState(tabs[0]?.id)
  const current = tabs.find((t) => t.id === selected) ?? tabs[0]
  if (!current) return null

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
    document.getElementById(`${base}-tab-${tabs[target].id}`)?.focus()
  }

  return (
    <div className={`tabs ${level}`}>
      <div role="tablist" aria-label={label} className="tablist">
        {tabs.map((tab, index) => (
          <button
            key={tab.id}
            id={`${base}-tab-${tab.id}`}
            type="button"
            role="tab"
            aria-selected={tab.id === current.id}
            aria-controls={`${base}-panel-${tab.id}`}
            tabIndex={tab.id === current.id ? 0 : -1}
            onClick={() => setSelected(tab.id)}
            onKeyDown={(e) => onKeyDown(e, index)}
          >
            {tab.label}
            {tab.count !== undefined && <span className="tab-count num"> ({tab.count})</span>}
          </button>
        ))}
      </div>
      <div
        role="tabpanel"
        id={`${base}-panel-${current.id}`}
        aria-labelledby={`${base}-tab-${current.id}`}
        className="tabpanel"
      >
        {current.content}
      </div>
    </div>
  )
}
