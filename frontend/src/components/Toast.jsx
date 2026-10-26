import { createContext, useCallback, useContext, useMemo, useState } from 'react'
import { CheckCircle2, AlertOctagon, X } from 'lucide-react'

const ToastContext = createContext({ notify: () => {} })

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const dismiss = useCallback((id) => setToasts((t) => t.filter((x) => x.id !== id)), [])

  const notify = useCallback(
    (message, { tone = 'success', timeout = 4000 } = {}) => {
      const id = Math.random().toString(36).slice(2)
      setToasts((t) => [...t.slice(-3), { id, message, tone }])
      if (timeout) setTimeout(() => dismiss(id), timeout)
    },
    [dismiss],
  )

  const value = useMemo(() => ({ notify }), [notify])

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        className="pointer-events-none fixed right-4 bottom-4 left-4 z-[60] flex flex-col items-end gap-2 sm:left-auto"
        aria-live="polite"
      >
        {toasts.map((t) => (
          <div
            key={t.id}
            className="pointer-events-auto flex w-full max-w-sm items-start gap-2 rounded-md bg-hull px-4 py-3 text-sm text-white shadow-lg"
          >
            {t.tone === 'error' ? (
              <AlertOctagon className="mt-0.5 size-4 shrink-0 text-[#ff9b9b]" aria-hidden />
            ) : (
              <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-signal" aria-hidden />
            )}
            <span className="flex-1">{t.message}</span>
            <button type="button" onClick={() => dismiss(t.id)} aria-label="Dismiss" className="text-white/70 hover:text-white">
              <X className="size-4" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export const useToast = () => useContext(ToastContext)
