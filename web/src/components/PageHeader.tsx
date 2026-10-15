import type { ReactNode } from 'react'
import { TitleReveal } from './brand/TitleReveal'

/** Brass step line, Limelight screen title, then a hairline (docs/BRAND.md, app layout).
 * `action` sits at the right of the title; `children` go below it. */
export function PageHeader({
  step,
  title,
  action,
  children,
}: {
  step: string
  title: string
  action?: ReactNode
  children?: ReactNode
}) {
  return (
    <header className="flex flex-col gap-5 border-b border-line pb-8">
      <div className="flex flex-wrap items-end justify-between gap-x-8 gap-y-5">
        <div className="flex min-w-0 flex-col gap-3">
          <span className="marquee-label">{step}</span>
          <h1
            className="text-[40px] leading-[48px] text-ink sm:text-[54px] sm:leading-[64px]"
          >
            <TitleReveal text={title} />
          </h1>
        </div>
        {action}
      </div>
      {children}
    </header>
  )
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <p role="alert" className="m-0 border-l-2 border-signal bg-surface-deep px-4 py-3 text-ink">
      {message}
    </p>
  )
}

/** A section heading in Limelight with an optional small note at the right. */
export function SectionHead({ id, title, note }: { id: string; title: string; note?: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4">
      <h2 id={id} className="text-[29px] leading-9 text-ink">
        {title}
      </h2>
      {note && <span className="meta">{note}</span>}
    </div>
  )
}
