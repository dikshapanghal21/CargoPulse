import { useCallback, useEffect, useRef, useState } from 'react'
import { parseApiError } from '../api/client'

/**
 * Run an async loader and track { data, error, loading }.
 * Re-runs whenever `deps` change; stale responses are ignored.
 */
export function useApi(loader, deps = [], { keepPrevious = true } = {}) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const requestId = useRef(0)

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const run = useCallback(loader, deps)

  const load = useCallback(
    async ({ silent = false } = {}) => {
      const id = ++requestId.current
      if (!silent) setLoading(true)
      if (!keepPrevious) setData(null)
      try {
        const result = await run()
        if (id === requestId.current) {
          setData(result)
          setError(null)
        }
      } catch (err) {
        if (id === requestId.current) setError(parseApiError(err))
      } finally {
        if (id === requestId.current) setLoading(false)
      }
    },
    [run, keepPrevious],
  )

  useEffect(() => {
    load()
  }, [load])

  return { data, error, loading, reload: load, setData }
}

export function useDebounced(value, delay = 300) {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(t)
  }, [value, delay])
  return debounced
}
