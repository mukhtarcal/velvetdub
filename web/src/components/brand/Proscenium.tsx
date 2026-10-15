'use client'

import { useEffect, useState, type ReactNode } from 'react'
import { cn } from '@/lib/utils'
import { Curtains, Valance } from './Curtains'

/**
 * A full-width stage that breaks out of the page column: valance across the top, drapes at the
 * sides, seats along the bottom. `open` draws the curtains back; `openOnArrival` opens them a
 * beat after the page appears, so you see them part. Children sit centre stage, above the drapes
 * when the curtains are shut and between them when open.
 */
export function Proscenium({
  open,
  openOnArrival = false,
  animate = true,
  seats = false,
  className,
  backdrop,
  children,
}: {
  open?: boolean
  openOnArrival?: boolean
  animate?: boolean
  seats?: boolean
  className?: string
  /** Drawn behind the curtains (the picture). */
  backdrop?: ReactNode
  children?: ReactNode
}) {
  const [arrived, setArrived] = useState(false)
  useEffect(() => {
    if (!openOnArrival) return
    const timer = window.setTimeout(() => setArrived(true), 350)
    return () => window.clearTimeout(timer)
  }, [openOnArrival])

  const isOpen = open ?? arrived

  return (
    <section
      className={cn(
        'relative mx-[calc(50%-50vw)] w-screen overflow-hidden bg-stage-black',
        className,
      )}
    >
      {backdrop && <div className="absolute inset-x-0 top-[70px] bottom-0" aria-hidden="true">{backdrop}</div>}
      <Curtains open={isOpen} animate={animate} />
      <div className="pointer-events-none absolute inset-x-0 top-0 z-[3] h-[64px] sm:h-[82px]">
        <Valance />
      </div>
      {seats && <Seats />}
      <div className="relative z-[4] flex h-full flex-col items-center justify-center px-6 pt-24 pb-28 text-center sm:px-[20%] sm:pb-32">
        {children}
      </div>
    </section>
  )
}

/** Two staggered rows of seat backs under the stage (docs/BRAND.md: landing stage only). */
function Seats() {
  const back = Array.from({ length: 22 })
  return (
    <svg
      className="pointer-events-none absolute inset-x-0 bottom-0 z-[3] h-[60px] w-full sm:h-[84px]"
      viewBox="0 0 1100 84"
      preserveAspectRatio="xMidYMax slice"
      aria-hidden="true"
    >
      {back.map((_, i) => (
        <rect key={`b${i}`} x={i * 50 + 2} y={18} width={44} height={70} rx={14} fill="var(--velvet-deep)" />
      ))}
      {back.map((_, i) => (
        <rect key={`f${i}`} x={i * 50 - 23} y={40} width={44} height={60} rx={14} fill="var(--velvet-mid)" />
      ))}
      <rect x="0" y="0" width="1100" height="1" fill="var(--gilt)" opacity="0.5" />
    </svg>
  )
}
