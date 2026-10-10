import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { BackIcon } from '../components/Icons'
import { Player } from '../components/player/Player'
import { ErrorNote } from '../components/PageHeader'
import { useAsync } from '../hooks/useAsync'
import { useSelectedProfile } from '../hooks/useSelectedProfile'

export function WatchPage() {
  const { titleId = '' } = useParams()
  const [profileId, changeProfile] = useSelectedProfile()
  const profiles = useAsync(() => api.listProfiles(), [])
  const playback = useAsync(() => api.playback(titleId, profileId), [titleId, profileId])

  return (
    <div className="watch">
      <header className="title-bar">
        <Link to="/" className="text">
          <BackIcon /> Library
        </Link>
        <h1>{playback.data?.name ?? ''}</h1>
      </header>
      {playback.error && <ErrorNote message={playback.error} />}
      {playback.data && (
        <Player
          info={playback.data}
          profiles={profiles.data ?? [playback.data.profile]}
          onProfileChange={changeProfile}
          onKeep={async (ids) => {
            await Promise.all(ids.map((id) => api.keepEvent(titleId, id)))
          }}
        />
      )}
    </div>
  )
}
