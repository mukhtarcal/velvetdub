import type { ReactNode } from 'react'

/** Brass step line, Limelight screen title, then a hairline (docs/BRAND.md, app layout).
 * `action` sits at the right of the title; `children` go below it. */
export function PageHeader({
  step,
  title,
  action,
  live,
  children,
}: {
  step: string
  title: string
  action?: ReactNode
  /** Announce a change of title to screen readers (the processing heading does this). */
  live?: boolean
  children?: ReactNode
}) {
  const heading = (
    <div className="page-heading">
      <span className="marquee-label">{step}</span>
      <h1 aria-live={live ? 'polite' : undefined}>{title}</h1>
    </div>
  )
  return (
    <header className="page-header">
      {action ? (
        <div className="page-header-row">
          {heading}
          {action}
        </div>
      ) : (
        heading
      )}
      {children}
    </header>
  )
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <p role="alert" className="error-note">
      {message}
    </p>
  )
}
