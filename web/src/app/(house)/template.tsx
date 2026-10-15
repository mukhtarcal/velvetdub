'use client'

import { motion } from 'motion/react'
import { EASE } from '@/lib/motion'

/** Each page rises in as you arrive, like the house lights going down. A template remounts on
 * every navigation, so this plays once per page. */
export default function HouseTemplate({ children }: { children: React.ReactNode }) {
  return (
    <motion.div
      className="flex flex-col gap-10"
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.55, ease: EASE }}
    >
      {children}
    </motion.div>
  )
}
