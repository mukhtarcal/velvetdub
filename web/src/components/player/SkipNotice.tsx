'use client'

import { useState } from 'react'
import { motion } from 'motion/react'
import { EASE } from '@/lib/motion'

export interface SkipNoticeData {
  /** Ids of the detections inside the skipped region. */
  ids: string[]
  seconds: number
  label: string
  notes: string[]
}

/** “Skipped 42 s” in signal, then the category, then two text actions (docs/BRAND.md). */
export function SkipNotice({ notice, onKeepIn }: { notice: SkipNoticeData; onKeepIn: () => void }) {
  const [explaining, setExplaining] = useState(false)

  return (
    <motion.div
      role="status"
      className="absolute bottom-4 left-4 z-10 max-w-[min(420px,85%)] border border-line border-l-2 border-l-signal bg-surface-deep/95 px-4 py-3 sm:bottom-6 sm:left-6"
      initial={{ opacity: 0, x: -16 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.35, ease: EASE }}
    >
      <p className="m-0 text-ink">
        <span className="font-bold text-signal tabular-nums">Skipped {notice.seconds} s</span> of {notice.label}
      </p>
      {explaining && (
        <p className="meta m-0 mt-1">{notice.notes.length > 0 ? notice.notes.join('. ') : 'No description was recorded.'}</p>
      )}
      <div className="flex gap-5">
        <button type="button" className="text-action min-h-11 cursor-pointer" onClick={() => setExplaining((v) => !v)}>
          What happened?
        </button>
        <button type="button" className="text-action min-h-11 cursor-pointer" onClick={onKeepIn}>
          Keep it in
        </button>
      </div>
    </motion.div>
  )
}
