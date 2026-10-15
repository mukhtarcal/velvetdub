'use client'

import { useState } from 'react'
import { Harbor } from './Harbor'

/** A picture from the film for a title, or the harbor scene when none could be made. */
export function Poster({ titleId, fallbackMoon }: { titleId: string; fallbackMoon: number }) {
  const [failed, setFailed] = useState(false)
  return (
    <div className="absolute inset-0">
      {failed ? (
        <Harbor moon={fallbackMoon} />
      ) : (
        // A plain img: the poster comes from the local API, there is nothing to optimise.
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={`/api/titles/${encodeURIComponent(titleId)}/media/poster`}
          alt=""
          loading="lazy"
          className="size-full object-cover transition-transform duration-700 ease-out group-hover:scale-[1.04]"
          onError={() => setFailed(true)}
        />
      )}
    </div>
  )
}
