'use client'

import Link from 'next/link'
import { motion } from 'motion/react'
import { ChevronLeft } from 'lucide-react'
import { api } from '@/api/client'
import { Valance } from '@/components/brand/Curtains'
import { ErrorNote } from '@/components/PageHeader'
import { Player } from '@/components/player/Player'
import { useAsync } from '@/hooks/useAsync'

/** Full-screen player: title bar above the stage, the valance over the screen, controls below a
 * velvet rule (docs/BRAND.md). The valance sits above the picture, never on it. */
export function WatchView({ titleId }: { titleId: string }) {
  const playback = useAsync(() => api.playback(titleId), [titleId])

  return (
    <div className="flex min-h-svh flex-col bg-stage-black">
      <header className="flex items-center gap-4 border-b border-line bg-ground px-3 py-2 sm:gap-6 sm:px-6">
        <Link href="/library" className="text-action inline-flex min-h-11 items-center gap-1">
          <ChevronLeft className="size-5" aria-hidden="true" /> Library
        </Link>
        <h1 className="m-0 truncate text-[22px] leading-8 text-ink sm:text-[29px]">{playback.data?.name ?? ''}</h1>
      </header>
      <div className="relative h-[60px] shrink-0 sm:h-[82px]">
        <Valance />
      </div>
      {playback.error && (
        <div className="p-6">
          <ErrorNote message={playback.error} />
        </div>
      )}
      {playback.data && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.8 }}>
          <Player
            info={playback.data}
            onKeep={async (ids) => {
              await api.keepEvents(titleId, ids, true)
            }}
          />
        </motion.div>
      )}
    </div>
  )
}
