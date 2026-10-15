'use client'

import { MotionConfig } from 'motion/react'

/** Every motion component follows the viewer's reduced-motion setting. CSS loops follow it in
 * styles/stage.css. */
export function MotionProvider({ children }: { children: React.ReactNode }) {
  return <MotionConfig reducedMotion="user">{children}</MotionConfig>
}
