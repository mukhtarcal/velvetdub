'use client'

import { motion } from 'motion/react'
import { EASE } from '@/lib/motion'

/** A Limelight title that arrives word by word (after Aceternity's text-generate effect, with
 * opacity and movement only: the brand allows no blur or glow). Screen readers get the whole title
 * from a hidden copy; the animated words are hidden from them. A new title replays the reveal. */
export function TitleReveal({ text, delay = 0.08 }: { text: string; delay?: number }) {
  const words = text.split(' ')
  return (
    <span key={text} className="inline">
      <span className="sr-only">{text}</span>
      <span aria-hidden="true">
      {words.map((word, i) => (
        <span key={i}>
          <motion.span
            className="inline-block"
            initial={{ opacity: 0, y: '0.35em' }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: delay + i * 0.07, ease: EASE }}
          >
            {word}
          </motion.span>
          {i < words.length - 1 ? ' ' : ''}
        </span>
      ))}
      </span>
    </span>
  )
}
