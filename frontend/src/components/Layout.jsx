import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { Bell, Gauge, Menu, Package, Route as RouteIcon, Search, Truck, X } from 'lucide-react'
import { ALERTS_CHANGED, api } from '../api'
import { parseApiError } from '../api/client'

export function Logo({ className = '' }) {
  return (
    <span className={`flex items-center gap-2.5 ${className}`}>
      <svg viewBox="0 0 32 32" className="size-8 shrink-0" aria-hidden>
        <rect x="1" y="1" width="30" height="30" rx="5" fill="#1d3954" />
        <rect x="5" y="9" width="22" height="14" rx="1.5" fill="none" stroke="#f2a900" strokeWidth="2" />
        <path
          d="M7 16h5l2-4 3 8 2-4h6"
          fill="none"
          stroke="#fff"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      <span className="stencil text-[1.15rem] font-extrabold tracking-tight text-white">CargoPulse</span>
    </span>
  )
}

const NAV = [
  { to: '/', label: 'Dashboard', icon: Gauge, end: true },
  { to: '/shipments', label: 'Shipments', icon: Package },
  { to: '/alerts', label: 'Alerts', icon: Bell, badge: 'alerts' },
  { to: '/carriers', label: 'Carriers', icon: Truck },
  { to: '/routes', label: 'Routes', icon: RouteIcon },
]

function TrackLookup({ onDone }) {
  const [value, setValue] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const navigate = useNavigate()

  async function submit(e) {
    e.preventDefault()
    const id = value.trim()
    if (!id) return
    setBusy(true)
    setError(null)
    try {
      const shipment = await api.shipments.byTracking(id)
      setValue('')
      onDone?.()
      navigate(`/shipments/${shipment.id}`)
    } catch (err) {
      const parsed = parseApiError(err)
      setError(parsed.status === 404 ? `No shipment ${id.toUpperCase()}` : parsed.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="px-3">
      <label htmlFor="track" className="mb-1.5 block text-[0.78rem] font-medium text-white/60">
        Track a shipment
      </label>
      <div className="relative">
        <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-white/50" />
        <input
          id="track"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Tracking ID"
          disabled={busy}
          className="code h-9 w-full rounded-md border border-white/15 bg-white/5 pr-2 pl-8 text-[0.85rem] text-white placeholder:font-normal placeholder:tracking-normal placeholder:text-white/40 focus:border-signal focus:outline-none"
        />
      </div>
      {error && <p className="mt-1.5 text-[0.78rem] text-[#ffc46b]">{error}</p>}
    </form>
  )
}

function SystemStatus() {
  const [health, setHealth] = useState(null)
  useEffect(() => {
    let alive = true
    const check = () =>
      api
        .health()
        .then((h) => alive && setHealth(h))
        .catch((err) => {
          const data = err?.response?.data
          if (alive) setHealth(data?.checks ? data : { status: 'down' })
        })
    check()
    const t = setInterval(check, 30000)
    return () => {
      alive = false
      clearInterval(t)
    }
  }, [])
  const ok = health?.status === 'ok'
  const text = !health ? 'Checking API…' : ok ? 'All systems operational' : health.status === 'down' ? 'API unreachable' : 'Degraded: ' + Object.entries(health.checks || {}).filter(([, v]) => v !== 'ok').map(([k]) => k).join(', ')
  return (
    <div className="flex items-center gap-2 px-4 text-[0.78rem] text-white/60">
      <span
        className={`size-2 rounded-full ${!health ? 'bg-white/30' : ok ? 'bg-[#4cc27a]' : 'bg-signal'}`}
        aria-hidden
      />
      {text}
    </div>
  )
}

function Sidebar({ alertCount, onNavigate }) {
  return (
    <div className="flex h-full flex-col gap-6 bg-hull py-5">
      <div className="px-4">
        <Logo />
      </div>
      <TrackLookup onDone={onNavigate} />
      <nav aria-label="Main" className="flex flex-col gap-0.5 px-2">
        {NAV.map(({ to, label, icon: Icon, end, badge }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            onClick={onNavigate}
            className={({ isActive }) =>
              `group flex items-center gap-3 rounded-md px-3 py-2 text-[0.93rem] font-medium transition-colors ${
                isActive ? 'bg-white/10 text-white' : 'text-white/70 hover:bg-white/5 hover:text-white'
              }`
            }
          >
            {({ isActive }) => (
              <>
                <Icon className={`size-[18px] ${isActive ? 'text-signal' : ''}`} aria-hidden />
                <span className="flex-1">{label}</span>
                {badge === 'alerts' && alertCount > 0 && (
                  <span className="num rounded-full bg-signal px-2 py-px text-[0.72rem] font-bold text-hull">
                    {alertCount}
                  </span>
                )}
              </>
            )}
          </NavLink>
        ))}
      </nav>
      <div className="mt-auto">
        <SystemStatus />
      </div>
    </div>
  )
}

export default function Layout() {
  const [open, setOpen] = useState(false)
  const [alertCount, setAlertCount] = useState(0)
  const location = useLocation()

  useEffect(() => {
    let alive = true
    const load = () =>
      api.alerts
        .counts()
        .then((c) => alive && setAlertCount(c.active))
        .catch(() => {})
    load()
    const interval = setInterval(load, 60_000)
    window.addEventListener(ALERTS_CHANGED, load)
    return () => {
      alive = false
      clearInterval(interval)
      window.removeEventListener(ALERTS_CHANGED, load)
    }
  }, [location.pathname])

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[236px_1fr]">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded focus:bg-surface focus:px-3 focus:py-2"
      >
        Skip to content
      </a>
      <aside className="sticky top-0 hidden h-screen lg:block">
        <Sidebar alertCount={alertCount} />
      </aside>

      <header className="sticky top-0 z-40 flex items-center justify-between bg-hull px-4 py-3 lg:hidden">
        <Logo />
        <button
          type="button"
          className="rounded-md p-2 text-white hover:bg-white/10"
          onClick={() => setOpen(true)}
          aria-label="Open navigation"
        >
          <Menu className="size-6" />
        </button>
      </header>

      {open && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-hull/60" onClick={() => setOpen(false)} aria-hidden />
          <div className="absolute inset-y-0 left-0 w-72 max-w-[85vw]">
            <button
              type="button"
              className="absolute top-4 right-3 z-10 rounded-md p-1.5 text-white hover:bg-white/10"
              onClick={() => setOpen(false)}
              aria-label="Close navigation"
            >
              <X className="size-5" />
            </button>
            <Sidebar alertCount={alertCount} onNavigate={() => setOpen(false)} />
          </div>
        </div>
      )}

      <main id="main" className="min-w-0 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
        <div className="mx-auto max-w-[1360px]">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
