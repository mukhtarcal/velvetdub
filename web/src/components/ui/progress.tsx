'use client'

import * as React from 'react'
import { Progress as ProgressPrimitive } from 'radix-ui'
import { cn } from '@/lib/utils'

/** A thin bar on the track colour. Processing progress is one of signal's jobs (docs/BRAND.md). */
function Progress({ className, value, ...props }: React.ComponentProps<typeof ProgressPrimitive.Root>) {
  return (
    <ProgressPrimitive.Root
      data-slot="progress"
      value={value}
      className={cn('relative h-1.5 w-full overflow-hidden border border-line bg-track', className)}
      {...props}
    >
      <ProgressPrimitive.Indicator
        data-slot="progress-indicator"
        className="h-full w-full origin-left bg-signal transition-transform duration-700 ease-out"
        style={{ transform: `scaleX(${Math.max(0, Math.min(100, value ?? 0)) / 100})` }}
      />
    </ProgressPrimitive.Root>
  )
}

export { Progress }
