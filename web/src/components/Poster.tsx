import { useState } from 'react'
import { Harbor } from './Harbor'

/** A picture from the film for a title, or the harbor scene when none could be made. */
export function Poster({ titleId, fallbackMoon }: { titleId: string; fallbackMoon: number }) {
  const [failed, setFailed] = useState(false)
  return (
    <div className="poster-picture">
      {failed ? (
        <Harbor moon={fallbackMoon} />
      ) : (
        <img
          src={`/api/titles/${encodeURIComponent(titleId)}/media/poster`}
          alt=""
          loading="lazy"
          onError={() => setFailed(true)}
        />
      )}
    </div>
  )
}
