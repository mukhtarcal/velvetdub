import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { BackIcon } from '../components/Icons'
import { Player } from '../components/player/Player'
import { ErrorNote } from '../components/PageHeader'
import { useAsync } from '../hooks/useAsync'

export function WatchPage() {
  const { titleId = '' } = useParams()
  const playback = useAsync(() => api.playback(titleId), [titleId])

  return (
    <div className="watch">
      <header className="title-bar">
        <Link to="/library" className="text">
          <BackIcon /> Library
        </Link>
        <h1>{playback.data?.name ?? ''}</h1>
      </header>
      {playback.error && <ErrorNote message={playback.error} />}
      {playback.data && (
        <Player
          info={playback.data}
          onKeep={async (ids) => {
            await Promise.all(ids.map((id) => api.keepEvent(titleId, id)))
          }}
        />
      )}
    </div>
  )
}
