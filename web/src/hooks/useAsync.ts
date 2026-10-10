import { useCallback, useEffect, useState } from 'react'

export interface AsyncState<T> {
  data: T | null
  error: string | null
  loading: boolean
  reload: () => void
  setData: (value: T | null) => void
}

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : 'Something went wrong.'
}

/** Load data when the inputs change. `reload` fetches again; `setData` updates it locally. */
export function useAsync<T>(load: () => Promise<T>, inputs: readonly unknown[]): AsyncState<T> {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [version, setVersion] = useState(0)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    load()
      .then((value) => {
        if (!cancelled) {
          setData(value)
          setLoading(false)
        }
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          setError(messageOf(e))
          setLoading(false)
        }
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `load` is intentionally keyed by `inputs`
  }, [...inputs, version])

  const reload = useCallback(() => setVersion((v) => v + 1), [])
  return { data, error, loading, reload, setData }
}
