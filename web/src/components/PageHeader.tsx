import type { ReactNode } from 'react'

/** Brass step line, Limelight screen title, then a hairline (docs/BRAND.md, app layout). */
export function PageHeader({
  step,
  title,
  children,
}: {
  step: string
  title: string
  children?: ReactNode
}) {
  return (
    <header className="page-header">
      <span className="marquee-label">{step}</span>
      <h1>{title}</h1>
      {children}
      <hr className="hairline" />
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
