import { useCallback, useState } from 'react'

const KEY = 'velvetdub.profile'
const DEFAULT_PROFILE = 'family'

function initialProfile(): string {
  // ?profile=kids wins (handy for sharing a view), then the last choice, then the default.
  const fromUrl = new URLSearchParams(window.location.search).get('profile')
  if (fromUrl) return fromUrl
  try {
    return localStorage.getItem(KEY) ?? DEFAULT_PROFILE
  } catch {
    return DEFAULT_PROFILE // storage can be unavailable (private windows); it's only a convenience
  }
}

/** The viewer's chosen filter profile, remembered between pages and visits. */
export function useSelectedProfile(): [string, (id: string) => void] {
  const [profileId, setProfileId] = useState(initialProfile)

  const choose = useCallback((id: string) => {
    setProfileId(id)
    try {
      localStorage.setItem(KEY, id)
    } catch {
      // not worth surfacing
    }
  }, [])

  return [profileId, choose]
}
