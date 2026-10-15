import type { ReactNode } from 'react'

/** A filter panel: surface-deep with a velvet top rule, heading in signal (docs/BRAND.md). */
export function Panel({ id, title, note, children }: { id: string; title: string; note?: string; children: ReactNode }) {
  return (
    <section
      aria-labelledby={id}
      className="flex flex-col gap-5 border-t-2 border-velvet bg-surface-deep p-5 sm:p-7"
    >
      <div className="flex items-baseline justify-between gap-4">
        <h2 id={id} className="m-0 text-[29px] leading-9 text-signal">
          {title}
        </h2>
        {note && <span className="meta">{note}</span>}
      </div>
      {children}
    </section>
  )
}
