import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import type { ReviewFilterItem } from '../api/types'
import { useAsync } from './useAsync'

/** The cuts for one title, and the "Keep it in" controls that change them. Shared by the review
 * page and the download page, so a choice made on either shows on both. */
export function useCuts(titleId: string, onChanged?: () => void) {
  const review = useAsync(() => api.review(titleId), [titleId])
  const [error, setError] = useState<string | null>(null)
  const errorRef = useRef<HTMLDivElement>(null)

  // A failed click can be far below the note at the top, so bring it into view.
  useEffect(() => {
    if (error) errorRef.current?.scrollIntoView?.({ block: 'center' })
  }, [error])

  async function setKept(ids: string[], keep: boolean) {
    if (ids.length === 0) return
    setError(null)
    try {
      await api.keepEvents(titleId, ids, keep)
      review.reload()
      onChanged?.()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not update those moments.')
    }
  }

  const toggle = (f: ReviewFilterItem) => void setKept([f.id], !f.kept)

  return { review, error, errorRef, setKept: (ids: string[], keep: boolean) => void setKept(ids, keep), toggle }
}
